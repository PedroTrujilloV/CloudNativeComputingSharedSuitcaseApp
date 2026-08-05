# proyecto-base  

## Tabla de contenido

- [proyecto-base](#proyecto-base)
  - [Tabla de contenido](#tabla-de-contenido)
  - [Estructura del Proyecto](#estructura-del-proyecto)
  - [Archivo de configuración](#archivo-de-configuración)
  - [Estructura de cada aplicación](#estructura-de-cada-aplicación)

## Estructura del Proyecto

```
.
├── github/
│   └── workflows/          # Pipelines del repositorio
├── k8s/                    # Archivos para despliegue en k8s
├── docs/                   # Archivos de documentación técnica
├── <aplicación>            # Archivos de aplicación. Una carpeta por cada una.
├── vale.ini                # Configuración para Vale. NO MODIFICAR
├── config.yaml             # Configuración del repositorio. Modifíquelo como primera tarea
├── Makefile                # Scripts para evaluación. NO MODIFICAR las reglas actuales
└── README.md               # Este archivo
```

1. **github/workflows**: los archivos en esta carpeta no se pueden modificar a excepción del archivo `ci_evaluador_unit.yml` el cuál debe ser utilizado para agregar un job por cada aplicación.
   * `ci_evaluador_entrega1_k8s.yml` verifica configuración de k8s y ejecuta pruebas sobre cada aplicación. Su modificación anula su entrega.
   * `ci_evaluador_entrega1_docs.yml` verifica que los diagramas de la documentación contengan los componentes esperados, hace una revisión gramática sobre el contenido del markdown. Su modificación anula su entrega.
   * `ci_evaluador_unit.yml` ejecuta pruebas unitarias. Modifique este archivo agregando un job por aplicación.
2. **k8s**: Archivos de configuración y despliegue de sus aplicaciones. Puede crear un archivo por aplicación o todos en un mismo archivo. La decisión de la estructura es suya.
3. **docs**: Archivos de la documentación técnica. Debe existir un archivo `README.md` para que se genere la página de la documentación en `github pages` y la carpeta `diagrams` con los archivos `puml` en esta. La estructura de la documentación es decisión del equipo.
4. **<aplicación>**: Una carpeta por cada aplicación. A continuación se habla en más detalle de su estructura.
5. **makefile**: El archivo `makefile` es utilizado por los pipelines evaluadores, **NO** modifique los scripts que encontrará allí, pero si puede agregar nuevos si así lo requiere.

## Archivo de configuración

El archivo `config.yaml` es el archivo más importante en el repositorio. Este archivo contiene la configuración que se usa en los pipelines para evaluar su entrega y se define la calificación de cada miembro del equipo. Si este archivo no está correctamente configurado, su entrega no puede ser calificada y será de cero.

## Estructura de cada aplicación

Cada aplicación debe seguir las siguientes reglas:

1. Cada aplicación debe estar en una carpeta independente y construida en el lenguaje de su preferencia. En este repositorio encontrará cómo ejemplo la aplicación `pets_app` construida en `Python`, `Poetry`, `FastAPI` y `Pytest`.
2. Dentro de cada carpeta de aplicación debe estar el archivo `Dockerfile` que permite la ejecución de la aplicación. Este archivo debe estar en la raiz de la carpeta y no en otras ubicaciones.
3. El nombre de la carpeta es decisión libre del equipo pero debe estar registrado en el archivo `config.yaml` o de lo contrario no podrá ser evaluado.
4. El nombre y tag de cada imagen deben ser agregadas en el archivo `config.yaml` y deben corresponder a los mismos que se usan en la configuración de despliegue de k8s. Si la configuración de este archivo no es correcta, su evaluación fallará y la nota será de cero.

Lo invitamos a revisar el archivo `README.md` de la carpeta [pets](./pets_app/) donde encontrará la documentación para utilizar ese proyecto en `Python` como su ejemplo.
