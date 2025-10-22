from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # Abre o navegador (pode ser "Google Chrome", "Firefox" ou "webkit")
    navegador = p.chromium.launch(channel="chrome", headless=False)
    pagina = navegador.new_page()

    # Acessa um site de testes (um editor online, por exemplo)
    pagina.goto("https://codamos.com.br/")

    # Espera o site carregar
    pagina.wait_for_timeout(2000)

    # Interage com o campo de código (dentro de um iframe)
    pagina.frame_locator("#iframeResult").locator("body").fill("Automação com Playwright em Python!")

    # Faz um print da tela
    pagina.screenshot(path="print_playwright.png")

    print("✅ Automação com Playwright concluída!")

    navegador.close()
