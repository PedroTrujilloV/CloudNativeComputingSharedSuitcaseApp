# Pets - Proyecto ejemplo

Este proyecto es un ejemplo de una aplicación FastAPI que implementa una arquitectura hexagonal (también conocida como puertos y adaptadores) para gestionar la entidad Pet. La aplicación se ejecuta haciendo uso de docker y puede ser ejecutada directamente en su ambiente o haciendo uso de k8s.

Haciendo uso de este proyecto usted entenderá:

- Cómo construir una aplicación siguiendo los principios SOLID con tecnologías como Python, FastAPI, Poetry y Pytest.
- Cómo ejecutar la aplicación por medio de Docker siguiendo buenas prácticas como son: stages y rootless.
- Cómo hacer uso de postman para automatizar pruebas de API que pueden ser ejecutadas en cualquier ambiente.
- Cómo ejecutar la aplicación en minikube para posteriormente ser ejecutada en ambientes productivos de k8s.
- Cómo configurar pipelines en github que ejecute pruebas unitarias, linters en Python, y pruebas con newman sobre docker y minikube.

## Tabla de contenido

- [Pets - Proyecto ejemplo](#pets---proyecto-ejemplo)
  - [Tabla de contenido](#tabla-de-contenido)
  - [Requisitos](#requisitos)
  - [Estructura del Proyecto](#estructura-del-proyecto)
    - [Carpeta src](#carpeta-src)
      - [Domain](#domain)
      - [Adapters](#adapters)
      - [Entrypoints](#entrypoints)
      - [Configuración y ensamble](#configuración-y-ensamble)
      - [Errores](#errores)
    - [Configuración](#configuración)
  - [Ejecución de la aplicación](#ejecución-de-la-aplicación)
    - [1. Instale las dependencias:](#1-instale-las-dependencias)
    - [2. Ejecución](#2-ejecución)
  - [Ejecutar en Docker](#ejecutar-en-docker)
  - [Ejecutar en minikube](#ejecutar-en-minikube)
  - [API Endpoints](#api-endpoints)
  - [Pet Model](#pet-model)
  - [Pruebas](#pruebas)
    - [Unitarias](#unitarias)
    - [Integración](#integración)
  - [Pipelines](#pipelines)
  - [Cómo contribuir](#cómo-contribuir)
  - [Licencia](#licencia)
  - [Autor](#autor)


## Requisitos

- Python 3.11
- Poetry version 2.1.1
- Docker
- Postman

## Estructura del Proyecto

```
.
├── src/
│   ├── domain/             # Capa de dominio
│   │   ├── models/         # Modelos de dominio
│   │   ├── ports/          # Puertos (interfaces)
│   │   └── use_cases/      # Casos de uso
│   ├── adapters/           # Capa de adaptadores
│   │   └── database/       # Adaptador de base de datos
│   └── entrypoints/        # Puntos de entrada
│       └── api/            # API REST
├── tests/                  # Pruebas
├── Dockerfile              # Configuración de Docker
├── pyproject.toml          # Configuración de Poetry
└── README.md               # Este archivo
```

### Carpeta src

Esta carpeta contiene el código y la lógica de la aplicación que permite exponer el API y puede integrar otras aplicaciones o componentes si lo requiere.

#### Domain

Carpeta con la lógica de la aplicación. Si tu aplicación está diseñada para cocinar una receta, esta carpeta es la cocina. 

- `/domain/models`: Contiene las clases que representan las entidades necesarias para los casos de uso de la aplicación. Comúnmente estos modelos son usados para el almacenamiento en la base de datos, pero no deben confundirse, estas clases no deben estar acopladas a una base de datos en específico y solo representan las entidades que se van a manipular en los casos de uso. Será responsabilidad de los adaptadores transformarlas y almacenarlas en una determinada base de datos. En este ejemplo los modelos estarán soportados haciendo uso de pydantic por facilidad de validación e integración con FastAPI.

```python
# domain/models/pet.py
class Pet(BaseModel):
    """Pet domain model."""

    id: int | None = None
    name: str = Field(min_length=1, description="Name cannot be empty")
    type: PetType
    age: int = Field(gt=0, description="Age must be greater than 0")
    owner_name: str = Field(min_length=1, description="Owner name cannot be empty")
```

- `/domain/ports`: Contiene las interfaces que habilitan la interacción con componentes o lógica externa. Estas clases no son implementaciones sino únicamente el "template" que deben seguir nuestras integraciones. Esto permite desacoplar la implementación, habilitando que se pueda reemplazar fácilmente los componentes con los que se integra la aplicación, siempre y cuando se respecte la definición de las interfaces. En este proyecto encontrará que se hace uso de una clase llamada [Repository](https://martinfowler.com/eaaCatalog/repository.html) la cual sigue un patrón que es comúnmente usado cuando el puerto es usado para almacenamiento de una entidad. Sin embargo, los puertos pueden seguir otros patrones para interactuar con otros componentes, por ejemplo notificaciones.

```python
# domain/ports/pet_repository_port.py
class PetRepositoryPort(ABC):
    """Pet repository interface."""

    @abstractmethod
    def create(self, pet: Pet) -> Pet:
        """Create a new pet."""
        pass
    ...

# another example
class NotificationDeliveryPort(ABC):
    """Designed to send notifications."""

    @abstractmethod
    def send(self, payload:Dict[str, str], title:str) -> bool:
        """Sends a notification."""
        pass
    ...
```

- `/domain/use_cases`: Contiene los casos de uso de la aplicación, almacenar, consultar, modificar, borrar o cualquier otra funcionalidad. Todos los casos de usos deben compartir el mismo contrato. Para ello deben extender de una interfaz que define como es el comportamiento de los casos de uso, esta interfaz resulta ser clave para permitir que los entrypoints de la aplicación puedan interactuar con los casos de uso sin generar acoplamiento.

```python
# domain/use_cases/base_use_case.py
class BaseUseCase(ABC):
    """Base use case class."""

    @abstractmethod
    def execute(self, *args, **kwargs):
        """Execute the use case."""
        pass

# domain/use_cases/create_pet_use_case.py
class CreatePetUseCase(BaseUseCase):
    """Use case for saving a pet."""

    def __init__(self, pet_repository: PetRepositoryPort):
        self.pet_repository = pet_repository

    def execute(self, pet: Pet) -> Pet:
        """Create a new pet."""
        return self.pet_repository.create(pet)
```
#### Adapters

En la carpeta adapters se encuentra la implementación de los puertos definidos en la carpeta de ports. En este proyecto de ejemplo se encuentra una implementación de un almacenamiento en memoria, pero usted puede seguir el mismo schema si quiere realizar una implementación para almacenar en una base de datos.

```python
# adapters/memory/pet_repository_adapter.py
class InMemoryPetRepositoryAdapter(PetRepositoryPort):
    """In memory implementation of PetRepository."""

    memory_store: Dict[int, Pet] = {}

    def sequence(self) -> int:
        """Generate a new sequence number."""
        return len(self.memory_store) + 1

    def create(self, pet: Pet) -> Pet:
        """Create a new pet."""
        pet.id = self.sequence()
        self.memory_store[pet.id] = pet
        return pet
    ...

# Another example
# Disclaimer: We suggest using Async Await if you plan to use SQL databases
class SQLAlchemyPetRepositoryAdapter(PetRepositoryPort):
    """SQL implementation of PetRepository."""
    def __init__(self, session: Session):
        self.session = session

    def create(self, pet: Pet) -> Pet:
        pet_model = pet_entity_to_model(pet)
        self.session.add(pet_model)
        self.session.commit()
        self.session.refresh(pet_model)
        return pet_model_to_entity(pet_model)
    ...
```

#### Entrypoints

Contiene los archivos que servirán como punto de acceso a la aplicación; también podrían considerarse como puertos de ingreso. En esta carpeta se encuentran las funciones o clases que permiten interactuar con los casos de uso. La implementación dependerá principalmente de la tecnología utilizada, cuando se trabaja con FastAPI normalmente se habla de Routers, mientras en Flask se encuentran los Blueprints.

En este proyecto se hace uso de routers donde se definen las rutas y los métodos HTTP que se soportan. Si usted quiere agregar nuevas rutas, debe agregar otro archivo router o modificar el actual siguiendo el mismo patrón.

```python
router = APIRouter(prefix="/pets")

@router.get("/ping", response_class=PlainTextResponse)
def health_check():
    """Healthcheck endpoint."""
    return "pong"
```

Posteriormente debe agregar el router a la aplicación en el archivo `main.py`

```python
app = FastAPI(title=Settings.app_name)
app.include_router(pet_router)
```

#### Configuración y ensamble

- `config.py`: En este archivo se encuentran las funciones que permiten leer las variables de ambiente o constantes que se usan en todo el proyecto. Es una buena práctica consolidar el manejo de las variables de ambiente y constantes a un solo archivo, facilita las pruebas y la mantenibilidad.
- `assembly.py`: Este archivo contiene las funciones que realizan la inyección de dependencias. Como ha podido ver en todos los ejemplos previos, las asociaciones entre las clases y funciones se realizan por medio de interfaces, ninguna clase conoce o usa una implementación en particular. Es en este paquete donde se instancian las implementaciones que se van a usar y las cuales son usadas por cada router:

```python
# assembly.py
repository: InMemoryPetRepositoryAdapter = InMemoryPetRepositoryAdapter()

def build_create_pet_use_case() -> BaseUseCase:
    """Get create pet use case."""
    return CreatePetUseCase(repository)
...

# entrypoints/api/routers/pet_router.py
@router.post("/", response_model=Pet)
def create_pet(
    pet: Pet, use_case: BaseUseCase = Depends(build_create_pet_use_case)
):
    """Create a new pet."""
    return use_case.execute(pet)
```

#### Errores

En el proyecto se encuentra el archivo `errors.py` el cual está diseñado para albergar todas las clases de excepciones personalizadas que se creen en el proyecto. Recomendamos crear sus propias clases de excepción para tener mayor control del flujo del programa.

```python
class PetNotFoundError(Exception):
    """Exception raised when a pet is not found."""
    pass
```

Haciendo uso de un handler de excepciones personalizado, puede indicarle a FastAPI que responda un error en particular cuando reciba este tipo de excepciones en un router.

```python
app = FastAPI(title=Settings.app_name)

@app.exception_handler(PetNotFoundError)
def pet_not_found_exception_handler(request: Request, exc: PetNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": exc.message},
    )
...
```

### Configuración

Este proyecto hace uso de [poetry](https://python-poetry.org/) para la gestión de dependencias y configuración de algunas librerías usadas en el proyecto. Encontrará la configuración en el archivo `pyproject.toml` el cuál ya es un estandar para la configuración de proyectos en Python. [Documentación](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/).

> Recomendación: procure evitar otros archivos de configuración como el `setup.cfg`, `setup.py`, `<archivo>.ini` u otros, con el fin de mejorar la mantenibilidad de nuestro código y evitar errores por conflictos de configuración.

Algunos puntos que tener en cuenta en la configuración:

- Agregue todas las dependencias que se usarán en producción en el group por defecto `[tool.poetry.dependencies]`. Esto sucederá por defecto al usar el comando add de poetry: 
```bash
poetry add <libreria>
```
- Agregue las dependencias de desarrollo en el grupo `dev`. Para esto defina el grupo cuando agregue la librería:
```bash
poetry add <librería> --group dev
```
- El archivo contiene las reglas de configuración de linters y herramientas de análisis habilitadas en el proyecto. `[tool.isort]`, `[tool.bandit]`, `[tool.pydoclint]`, `[tool.ruff]`. Si desea modificar las reglas o conocer más de ellas puede revisar los links en cada sección.
- El archivo contiene las reglas de configuración para la ejecución de pruebas con pytest. En la sección `[tool.pytest.ini_options]` puede modificar o agregar nuevas reglas de pruebas. Así como las variables de ambiente que se usarán en las pruebas.

Siempre que modifique el archivo, recomendamos regenerar el archivo de poetry.lock usando:
```bash
poetry lock
```

## Ejecución de la aplicación

### 1. Instale las dependencias:
```bash
poetry install

# Si no existe el archivo poetry.lock ejecute primero
# poetry lock
```
Poetry instalará todas las dependencias en un ambiente virtual gestionado por Poetry.

### 2. Ejecución

dado que todas las dependencias están instaladas en una ambiente virtualizado y gestionado por Poetry es necesario correr el servidor haciendo uso de Poetry:
```bash
PYTHONPATH=$(pwd)/src poetry run uvicorn entrypoints.api.main:app --host 0.0.0.0 --port 9000
```

El API estará disponible en `http://localhost:9000`

Cargue el archivo `pets_app/tests/api/pets.postman_collection.json` en su postman y reemplace la variable `baseUrl` por la url.

Ejecute las pruebas y verifique que se completa correctamente.

## Ejecutar en Docker

```bash
APP_VERSION = ... # use la misma versión del documento pyproject.toml
APP_NAME = ... # use el mismo definido en el documento pyproject.toml
docker build --rm --platform linux/amd64 -t ${APP_NAME}:${APP_VERSION} -f Dockerfile --target runner --label version=${APP_VERSION} .

docker run --platform linux/amd64 -p 9000:9000 ${APP_NAME}:${APP_VERSION}
```

## Ejecutar en minikube

Después de haber creado la imagen haciendo uso de docker, ejecute:

```bash
minikube start --cpus=2 --memory=3g --cni calico

#make mkbuild
minikube image load ${APP_NAME}:${APP_VERSION}

kubectl apply -f k8s
minikube service pets-service
```

Minikube asignará un puerto para que pueda acceder a su servicio. Puede usarlo en su browser o en postman.

## API Endpoints

- `POST /pets/` - Crea un Pet
- `GET /pets/{pet_id}` - Trae un Pet en específico
- `GET /pets/` - Trae todos los pets
- `PUT /pets/{pet_id}` - Modifica un pet
- `DELETE /pets/{pet_id}` - Borra un pet
  
Accede a la documentación después de ejecutar la aplicación:
- Swagger UI: `http://localhost:9000/docs`

## Pet Model

Un Pet tiene los siguientes campos:
- `id`: Integer (auto-generated)
- `name`: String
- `type`: Enum (dog, cat, bird, other)
- `age`: Integer
- `owner_name`: String

## Pruebas

El proyecto contempla dos paquetes de pruebas: pruebas unitarias y pruebas de API (Integración).

### Unitarias

Cree las pruebas usando la misma estructura de la carpeta src. Si la clase que va a probar es `domain/models/pet.py`, las pruebas deben estar ubicadas en `tests/unit/domain/models/test_pet.py`.

Si está usando pytest para sus pruebas, utilice [fixtures](https://docs.pytest.org/en/stable/explanation/fixtures.html) para crear recursos reutilizables en las pruebas. Esto mejorará su código y permitirá que las pruebas sean consistentes. Estos fixtures deben estar ubicados en un archivo `conftest.py` y no en los archivos de pruebas.

```python
# conftest.py
@pytest.fixture
def valid_pet_data():
    """Fixture providing valid pet data."""
    return {"name": "Rex", "type": PetType.DOG, "age": 5, "owner_name": "John Doe"}

# test_pet.py
def test_create_pet_with_valid_data(valid_pet_data):
    """Test creating a pet with valid data."""
    pet = Pet(**valid_pet_data)
    ...
```

Para ejecutar las pruebas unitarias y establecer el porcentaje mínimo de cobertura del conjunto de pruebas en 70%, ejecuta el siguiente comando:
```bash
poetry install
poetry run pytest --cov=src -v -s --cov-fail-under=70 --cov-report term-missing
```

Por último, recuerde que la configuración de pytest está en el archivo `pyproject.toml`, ajuste la sección dependiendo de las necesidades que tenga. Acuda a la [documentación](https://docs.pytest.org/en/stable/reference/customize.html) si lo requiere.

### Integración

Las pruebas de integración se realizan por medio de postman y newman. Encontrará un archivo de colección de postman en la carpeta `tests/api/` el cuál puede cargar en su aplicación de postman de manera local. Posteriormente puede ejecutar `Run collection` para verificar que la aplicación está funcionando correctamente.

Estas pruebas son ejecutadas de manera automática en los pipelines de pruebas.

## Pipelines

Utilice los ejemplos en la carpeta `.github/workflows/` de este repositorio para configurar sus pipelines. Estos pipelines son solo una guía y no son obligatorios para todos los proyectos. 

Para más información puede revisar la [documentación oficial](https://github.com/features/actions)

## Cómo contribuir

Sigue las reglas definidas en la carpeta .cursor para agregar nuevos features a este proyecto. Si tiene sugerencias o recomendaciones para mejorar los cursor rules le agradecemos nos las comparta.

## Licencia

Este proyecto está licenciado bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para más detalles.

## Autor

- César Forero - [ca.forero10@uniandes.edu.co](mailto:ca.forero10@uniandes.edu.co)