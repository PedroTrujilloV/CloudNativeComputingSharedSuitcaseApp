# Scripts locales (medida temporal)

Esta carpeta reemplaza, de forma temporal, la ejecución de los siguientes pipelines
directamente en la máquina del estudiante:

| Script | Reemplaza |
|---|---|
| `deploy.sh` | `ci_entrega2_deploy.yml` |
| `test-entrega3.sh` | `ci_evaluador_entrega3.yml` |
| `destroy.sh` | `ci_entrega2_destroy.yml` |
| `check-prerequisites.sh` | nuevo |

## 1. Instalación de esta carpeta en su repositorio

Copien toda la carpeta `scripts/` (tal cual, incluyendo `.env.example` y
`.gitignore`) en la **raíz** de su repositorio (junto a `config.yaml` y las
carpetas `terraform/`, `k8s/`, etc.). Pueden hacer commit y push de esta
carpeta sin problema: el único archivo que no debe subirse es `scripts/.env`,
y eso ya está resuelto por `scripts/.gitignore`.

## 2. Prerrequisitos

Los scripts son de bash y funcionan igual en macOS, Linux y Windows. En
**Windows deben ejecutarse con Git Bash** (se instala junto con Git para
Windows) o con WSL2; no funcionan en PowerShell ni en CMD.

Herramientas necesarias:

- `git`, `curl`, `jq`
- `aws` (AWS CLI v2)
- `yq` (la versión de mikefarah/yq v4; **no** la versión en Python)
- `terraform`
- `docker` (con el daemon corriendo; Docker Desktop en macOS/Windows)
- `kubectl`
- `helm`
- `envsubst` (parte del paquete `gettext`)
- `node`, `npm` y `newman` (`npm install -g newman`)

Para verificar qué falta, ejecuten:

```bash
bash scripts/check-prerequisites.sh all
```

También puede correrse con `deploy`, `destroy` o `test` en vez de `all` para
revisar solo lo que necesita cada script. `deploy.sh`, `destroy.sh` y
`test-entrega3.sh` ya invocan esta verificación automáticamente al iniciar.

### Instalación rápida por sistema operativo

**macOS** (con [Homebrew](https://brew.sh)):

```bash
brew install awscli terraform kubectl helm jq yq gettext node
brew link --force gettext
npm install -g newman
```

Docker Desktop se instala aparte: https://www.docker.com/products/docker-desktop

**Windows** (con [Chocolatey](https://chocolatey.org/install), desde una
terminal con permisos de administrador):

```powershell
choco install awscli terraform kubernetes-cli kubernetes-helm jq yq gettext nodejs-lts git
```

Docker Desktop se instala aparte, con la integración de WSL2 habilitada:
https://www.docker.com/products/docker-desktop

Luego, desde Git Bash:

```bash
npm install -g newman
```

**Linux**: instalen cada herramienta con el gestor de paquetes de su
distribución. `yq` casi siempre debe instalarse aparte del gestor de
paquetes del sistema (el paquete `yq` de muchas distribuciones es la versión
en Python, incompatible); descárguenlo desde
https://github.com/mikefarah/yq/releases

## 3. Configuración

Dentro de `scripts/`, copien el archivo de ejemplo y complétenlo:

```bash
cp scripts/.env.example scripts/.env
```

Edite `scripts/.env` con:

- `ENVIRONMENT`: `student1`, `student2`, `student3`, `student4` o `tutor`,
  según cuál les fue asignado.
- Las credenciales de AWS (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
  `AWS_SESSION_TOKEN`). En cuentas de AWS Academy son temporales y expiran
  cada pocas horas: si un script falla con un error de autenticación de AWS,
  generen credenciales nuevas y actualicen este archivo antes de reintentar.
- `DB_USERNAME`/`DB_PASSWORD` si sus stacks de terraform los requieren.
- `EMAIL_TO_NOTIFY` para `test-entrega3.sh`.
- `TF_STATE_BUCKET_NAME` y `REPO_NAME` solo si `ENVIRONMENT=tutor` (ver los
  comentarios de `scripts/.env.example`).
- Cualquier otro secret que usen sus stacks de terraform o su aplicación,
  con el mismo nombre que usarían como secret de GitHub.

El archivo `scripts/.env` nunca debe subirse al repositorio.

## 4. Uso

Desde la raíz del repositorio:

```bash
bash scripts/deploy.sh
```

Aprueben la suscripción del correo electrónico en caso que hayan utilizado un SNS para notificaciones. Y luego, para probar la entrega 3:

```bash
bash scripts/test-entrega3.sh
```

Al final, para destruir los recursos creados:
```bash
bash scripts/destroy.sh
```

> **NO** corran `deploy.sh` y `destroy.sh` del mismo ambiente al mismo tiempo, ni
> dos ejecuciones del mismo script en paralelo: pueden dañar el state de
> terraform o el cluster.

## 5. Diferencias frente al pipeline de GitHub Actions

- La versión de Terraform que se usa es la instalada en su máquina, no la
  fijada en `terraform/.terraform-version`. Los scripts advierten si no
  coinciden, pero no la instalan por ustedes.
- Las imágenes se construyen y publican una por una, no en paralelo.
- No existe el mecanismo de `concurrency` de GitHub Actions: eviten correr
  dos scripts sobre el mismo ambiente a la vez.
- `test-entrega3.sh` siempre usa `us-east-1`, igual que el workflow original.

## 6. Problemas comunes

- **Error de autenticación de AWS**: las credenciales temporales expiraron.
  Generen unas nuevas y actualicen `scripts/.env`.
- **Docker: `Cannot connect to the Docker daemon`**: abran Docker Desktop y
  esperen a que termine de iniciar.
- **`yq` con errores de sintaxis o de opciones desconocidas**: tienen
  instalada la versión en Python en vez de mikefarah/yq v4.
  `check-prerequisites.sh` avisa sobre esto.
- **`$'\r': command not found` o errores similares al ejecutar un script**:
  el archivo quedó con saltos de línea de Windows (CRLF). Conviértanlo a LF,
  por ejemplo con `dos2unix scripts/*.sh`, o configuren Git con
  `git config core.autocrlf input` antes de clonar de nuevo.
- **`Failed to query available provider packages` / `TLS handshake timeout`
  al conectarse a `registry.terraform.io`**: es un corte de red transitorio,
  no un error de los scripts. Vuelvan a ejecutar el script y listo.
