from playwright.sync_api import sync_playwright, TimeoutError
import os
import re
import json
from urllib.parse import urlparse
from pathlib import Path

URL = "https://codamos.com.br/"

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
        with open(dest_path, "wb") as f:
            f.write(resp.body())
        return True
    except Exception:
        return False

base_dir = Path(__file__).parent.resolve()
articles_dir = base_dir / "data" / "articles"
images_dir = base_dir / "data" / "images"

articles_dir.mkdir(parents=True, exist_ok=True)
images_dir.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto(URL, wait_until="networkidle")
    page.wait_for_timeout(1500)

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
        article_dir = os.path.join("data", "articles", safe_name)
        os.makedirs(article_dir, exist_ok=True)

        # Extrair conteúdo (texto)
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

        # Extrair imagem de capa
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

        # Salvar texto
        texto_path = os.path.join(article_dir, "texto.txt")
        with open(texto_path, "w", encoding="utf-8") as f:
            f.write(title + "\n\n")
            f.write(content)

        # Salvar screenshot
        screenshot_path = os.path.join(article_dir, "screenshot.png")
        try:
            article_page.screenshot(path=screenshot_path, full_page=True)
        except Exception:
            pass

        # Baixar imagem
        saved_image = None
        if img_url:
            parsed = urlparse(img_url)
            ext = os.path.splitext(parsed.path)[1] or ".jpg"
            image_filename = f"{safe_name}{ext}"
            image_path = os.path.join("data", "images", image_filename)
            ok = download_image(context.request, img_url, image_path)
            if ok:
                saved_image = image_path

        articles_summary.append({
            "title": title,
            "dir": article_dir,
            "texto": texto_path,
            "screenshot": screenshot_path if os.path.exists(screenshot_path) else None,
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
    with open(os.path.join("data", "articles_index.json"), "w", encoding="utf-8") as jf:
        json.dump(articles_summary, jf, ensure_ascii=False, indent=2)

    context.close()
    browser.close()
