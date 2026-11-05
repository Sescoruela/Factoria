La reproducción real con python -m unittest discover -s tests -v falla en dos de tres casos.
La condición number % 2 != 0 selecciona impares. [1,2,3,4] da 4 en vez de 6; [-4,-3,0,2] da -3 en vez de -2.
Alcance previsto: cambiar únicamente el predicado de app.py a == 0. No modificar pruebas, configuración ni archivos fuera de este repositorio de laboratorio.
La entrada vacía debe seguir devolviendo 0. Se utilizarán los comandos confirmados por la memoria para verificar.
