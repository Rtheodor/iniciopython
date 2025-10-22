import pyautogui
import subprocess
import time

# Abre o gedit
subprocess.Popen(['gedit'])

# Espera abrir
time.sleep(2)

# Digita texto
pyautogui.write("Olá! Este é um teste de automação com Python!", interval=0.05)

# Espera 1 segundo
time.sleep(1)

# Tira screenshot da tela
pyautogui.screenshot('print_automacao.png')

print("✅ Automação concluída com sucesso!")
