import pyautogui
import time

print("Mova o mouse para o botão 📞.")
print("Quando parar, a posição será salva automaticamente.")
print("")

ultima = pyautogui.position()

while True:
    atual = pyautogui.position()

    if atual != ultima:
        ultima = atual
        print(f"Mouse: X={atual.x} Y={atual.y}", flush=True)

    time.sleep(0.1)
