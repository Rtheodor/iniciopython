# automacao_web — resumo rápido

Descrição
- Script `automacao_web.py` usa Playwright para abrir a home do site, clicar em cada artigo, extrair título, texto e imagem de capa, salvar texto, screenshot e imagem em disco e gerar um índice JSON.

Pré-requisitos
- Python 3.8+
- Playwright (Python) e navegadores instalados

Instalação rápida
```bash
cd /home/diretorio/Desktop/projetos/iniciopython
python3 -m pip install --user playwright
python3 -m playwright install
```

Como executar
```bash
cd /home/diretorio/Desktop/projetos/iniciopython
python3 automacao_web.py
```

O que o script gera (pasta `data/`)
- `data/articles/<nome_do_artigo>/texto.txt`  — título + conteúdo
- `data/articles/<nome_do_artigo>/screenshot.png` — screenshot do artigo
- `data/images/<nome_do_artigo>.<ext>` — imagem de capa (se encontrada)
- `data/articles_index.json` — índice com resumo de todos os artigos salvos

Comandos úteis no Ubuntu para ver o resultado
```bash
# listar árvore de arquivos
ls -R data
# ou, se quiser mais legível:
sudo apt install -y tree && tree data

# ver índice formatado (instale jq se quiser)
sudo apt install -y jq && jq . data/articles_index.json

# ver inicio do texto de um artigo (substitua NOME_PASTA)
head -n 40 "data/articles/NOME_PASTA/texto.txt"

# abrir imagem/screenshot no visualizador padrão
xdg-open "data/articles/NOME_PASTA/screenshot.png"
xdg-open "data/images/NOME_PASTA.jpg"
```

Notas importantes
- Se o script não salvar nada, ajuste os seletores (`preview_selector`, seletores de `title` e `content`) para o HTML real da página.
- Em páginas lentas aumente timeouts (valores `timeout` e `wait_for_timeout`).
- O script clica nos links dos previews (abre na mesma aba ou em nova aba conforme o atributo `target`).
- Se precisar de logs mais verbosos ou transformar em testes (pytest), posso adaptar.

Contato rápido
- Este README é um lembrete rápido do que foi feito e como rodar. Ajuste seletores e timeouts conforme necessário.
