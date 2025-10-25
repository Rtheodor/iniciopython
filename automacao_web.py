from playwright.sync_api import sync_playwright, TimeoutError
import os
import re
import json
from urllib.parse import urlparse
from pathlib import Path


URL = "https://python.org.br/"

def sanitize_filename(s):
    s = (s or "").strip()
    s = re.sub(r"[^\w\-\.\s]+", "_", s)
    return s[:120].strip()

def download_image(request_ctx, url, dest_path):
    if not url:
        return False
    if url.startswith("//"):
        url = "https:" + url
    try:
        resp = request_ctx.get(url, timeout=15000)
        if resp.status != 200:
            return False
        dest_path = str(dest_path)  # aceitar Path ou str
        with open(dest_path, "wb") as f:
            f.write(resp.body())
        return True
    except Exception:
        return False

base_dir = Path(__file__).parent.resolve()

# novo: cria pasta por domínio (ex: data/quatrorodas_abril_com)
domain = urlparse(URL).netloc.replace(":", "_").replace(".", "_")
data_root = base_dir / "data" / domain
articles_dir = data_root / "articles"
images_dir = data_root / "images"

articles_dir.mkdir(parents=True, exist_ok=True)
images_dir.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=False)
    context = browser.new_context()
    page = context.new_page()

    # aumentar timeouts padrão para navegação e ações
    context.set_default_navigation_timeout(60000)   # 60s
    page.set_default_timeout(60000)

    # tentar abrir a página com fallback em caso de timeout
    try:
        page.goto(URL, wait_until="networkidle", timeout=60000)
    except TimeoutError:
        print("Aviso: timeout ao carregar com networkidle — tentando domcontentloaded...")
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        except TimeoutError:
            print("Erro: não foi possível carregar a página após tentativas. Salvando diagnóstico...")
            try:
                # salva screenshot e HTML para inspeção
                (data_root).mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(data_root / "error_screenshot.png"))
                html = page.content()
                (data_root / "error_page.html").write_text(html, encoding="utf-8")
                print("Diagnóstico salvo em:", data_root)
            except Exception as e:
                print("Falha ao salvar diagnóstico:", e)
            raise

    page.wait_for_timeout(1500)

    # Fechar banner de cookies se presente (Diolinux usa .cc-btn.cc-dismiss)
    try:
        cookie = page.locator(".cc-btn.cc-dismiss")
        if cookie.count() and cookie.first.is_visible():
            cookie.first.click(timeout=3000)
            page.wait_for_timeout(800)
            print("Banner de cookies dispensado.")
    except Exception:
        # fallback: remover via JS se o click não funcionar
        try:
            page.evaluate("document.querySelectorAll('.cc-window, .cc-banner, .cookieconsent').forEach(e => e.remove())")
            page.wait_for_timeout(300)
            print("Banner de cookies removido via JS.")
        except Exception:
            pass

    # --- diagnóstico: imprimir contagens de seletores e tentar scroll se necessário ---
    candidate_selectors = [
        "article", ".post", ".card", ".blog-item", ".entry",
        ".td-block-row .td-module-container", ".td_module_wrap", ".post-listing .post",
        ".post-item", ".blog-list .item", ".content .post"
    ]

    print(">> Diagnosticando seletores na home:", URL)
    any_found = False
    for sel in candidate_selectors:
        try:
            n = page.locator(sel).count()
        except Exception:
            n = 0
        print(f"  {sel} -> {n}")
        if n:
            any_found = True

    # Se nada encontrado, tenta scroll/pause (lazy load) e reconta
    if not any_found:
        print("  Nenhum preview encontrado — rolando a página e aguardando conteúdo dinâmico...")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)
        for sel in candidate_selectors:
            try:
                n = page.locator(sel).count()
            except Exception:
                n = 0
            print(f"  after-scroll {sel} -> {n}")

    # Se ainda nada, imprime um trecho do HTML para inspecionar manualmente
    if not any_found:
        try:
            snippet = page.locator("body").first.inner_html(timeout=2000)[:2000]
            print("  Trecho do HTML da página (primeiros 2000 chars):")
            print(snippet)
        except Exception as e:
            print("  Não foi possível obter HTML:", e)
    # --- fim diagnóstico ---

    articles_summary = []

    # Seletores flexíveis para encontrar previews na home
    preview_selector = "article, .post, .card, .blog-item, .entry"

    previews = page.locator(preview_selector)
    total = previews.count()
    if total == 0:
        # fallback: procurar links de post na home
        previews = page.locator("a[href*='/'] >> xpath=..")
        total = previews.count()

    for index in range(total):
        # Re-obter previews (DOM pode mudar)
        previews = page.locator(preview_selector)
        if index >= previews.count():
            break

        preview = previews.nth(index)
        link = preview.locator("a").first
        if not link:
            continue

        target = link.get_attribute("target")
        opened_new_page = None
        article_page = None

        try:
            if target == "_blank":
                with context.expect_page() as new_page_info:
                    link.click()
                opened_new_page = new_page_info.value
                article_page = opened_new_page
                article_page.wait_for_load_state("domcontentloaded", timeout=10000)
            else:
                with page.expect_navigation(timeout=10000):
                    link.click()
                article_page = page
                article_page.wait_for_load_state("networkidle", timeout=10000)
        except TimeoutError:
            print(f"Aviso: timeout ao abrir o artigo #{index}")
            if opened_new_page:
                opened_new_page.close()
            continue
        except Exception as e:
            print(f"Aviso: erro ao abrir o artigo #{index}: {e}")
            if opened_new_page:
                opened_new_page.close()
            continue

        # Extrair título
        title = ""
        try:
            for sel in ["article h1", "h1.entry-title", "h1", ".post-title", ".entry-title"]:
                try:
                    loc = article_page.locator(sel).first
                    title = loc.inner_text(timeout=1500).strip()
                    if title:
                        break
                except Exception:
                    title = ""
            if not title:
                title = article_page.title().strip() or f"artigo_{index}"
        except Exception:
            title = f"artigo_{index}"

        safe_name = sanitize_filename(title) or f"artigo_{index}"

        # --- NOVO: extrair conteúdo (texto) ---
        content = ""
        try:
            for s in ["article .entry-content", ".entry-content", ".post-content", ".content", "#content", "article"]:
                try:
                    txt = article_page.locator(s).first.inner_text(timeout=1500).strip()
                    if txt and len(txt) > 30:
                        content = txt
                        break
                except Exception:
                    continue
            if not content:
                content = article_page.locator("body").inner_text().strip()
        except Exception:
            content = ""
        # --- fim extração de conteúdo ---

        # --- NOVO: extrair imagem de capa ---
        img_url = None
        try:
            for s in ["article img", ".post-thumbnail img", ".featured img", "img.wp-post-image", ".entry-image img", "img"]:
                try:
                    img = article_page.locator(s).first
                    src = img.get_attribute("src") or img.get_attribute("data-src") or img.get_attribute("data-lazy-src")
                    if src:
                        img_url = src
                        break
                except Exception:
                    continue
        except Exception:
            img_url = None
        # --- fim extração de imagem ---

        # usar pathlib para salvar dentro de data/<domínio>/articles
        article_dir = articles_dir / safe_name
        article_dir.mkdir(parents=True, exist_ok=True)

        # Salvar texto
        texto_path = article_dir / "texto.txt"
        with open(texto_path, "w", encoding="utf-8") as f:
            f.write(title + "\n\n")
            f.write(content)

        # Salvar screenshot
        screenshot_path = article_dir / "screenshot.png"
        try:
            article_page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            pass

        # Baixar imagem (salvar em data/<domínio>/images)
        saved_image = None
        if img_url:
            parsed = urlparse(img_url)
            ext = os.path.splitext(parsed.path)[1] or ".jpg"
            image_filename = f"{safe_name}{ext}"
            image_path = images_dir / image_filename
            ok = download_image(context.request, img_url, image_path)
            if ok:
                saved_image = str(image_path)

        articles_summary.append({
            "title": title,
            "dir": str(article_dir),
            "texto": str(texto_path),
            "screenshot": str(screenshot_path) if screenshot_path.exists() else None,
            "image_saved": saved_image,
        })

        print(f"Salvo: {title}")

        # Fechar aba extra ou voltar para a home
        try:
            if opened_new_page:
                opened_new_page.close()
                page.goto(URL, wait_until="networkidle")
            else:
                page.go_back(timeout=10000)
                page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            page.goto(URL, wait_until="networkidle")

        page.wait_for_timeout(600)

    # Salvar índice
    with open(data_root / "articles_index.json", "w", encoding="utf-8") as jf:
        json.dump(articles_summary, jf, ensure_ascii=False, indent=2)

    context.close()
    browser.close()
