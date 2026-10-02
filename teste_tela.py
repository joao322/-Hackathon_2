import pyautogui
import time

print("TESTE INICIADO")
print("Mova o mouse.")
print("Pressione CTRL+C para parar.")

while True:
    x, y = pyautogui.position()
    print("X =", x, "Y =", y, flush=True)
    time.sleep(1)
