# Plan de feature-lab aprobado para implementar

1. Añadir count_even(numbers) en app.py: contar enteros cuyo resto módulo 2 sea cero. Conservar sum_even sin cambios.
2. Añadir tests/test_count_even.py con casos de entrada vacía, lista mixta, negativos y cero. No editar tests/test_app.py ni acceptance_feature.py.
3. Ejecutar los dos comandos confirmados por Factoría: python -m unittest discover -s tests -v y python acceptance_feature.py.
4. Revisar diff y resultados, registrar review.json y propuesta de documentación. Esperar aprobación humana final antes del cierre y autorización separada antes de commit.

Criterios: count_even([1,2,4,-2,0]) == 4, count_even([]) == 0, count_even([-3,-2,-1]) == 1. sum_even conserva sus tres pruebas actuales.
Riesgo: confundir pares con impares o excluir el cero; cubierto por las comprobaciones. Sin dependencias externas ni acceso a servicios.
Aprobado por el usuario con «Sí» después de presentar este plan. Implementación y verificación completadas; aprobación final y commit local pendientes.
