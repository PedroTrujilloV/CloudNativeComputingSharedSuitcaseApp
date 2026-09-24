variable "aws_region" {
  description = "La región de AWS donde se desplegarán los recursos."
  type        = string
  nullable    = false
}

variable "owner" {
  description = "Propietario de los recursos, generalmente el nombre del usuario o equipo."
  type        = string
  nullable    = false
}

variable "lambda_function_name" {
  description = "Nombre de la función Lambda del worker de verificación de tarjetas."
  type        = string
  nullable    = false
}

variable "lambda_role_name" {
  description = "Nombre del rol IAM de ejecución del worker (permiso mínimo)."
  type        = string
  nullable    = false
}

variable "image_repository_name" {
  description = "Nombre del repositorio ECR de la imagen del worker (creado por 2_registry)."
  type        = string
  nullable    = false
}

variable "image_tag" {
  description = "Tag de la imagen del worker en ECR (el mismo que la entrada card_worker de config.yaml)."
  type        = string
  nullable    = false
}

variable "credit_cards_table_name" {
  description = "Nombre de la tabla DynamoDB de las tarjetas (creada por 3_dynamodb); solo se usa para resolver su ARN."
  type        = string
  nullable    = false
}

variable "card_verification_topic_name" {
  description = "Nombre del topic SNS del resultado de la verificación de tarjetas (creado por 4_sns); solo se usa para resolver su ARN."
  type        = string
  nullable    = false
}

variable "queue_name" {
  description = "Nombre de la cola SQS de eventos de verificación (creada por 5_sqs); solo se usa para resolver su ARN."
  type        = string
  nullable    = false
}

variable "poll_max_attempts" {
  description = "Intentos de polling acotados por invocación del worker."
  type        = number
}

variable "poll_interval_seconds" {
  description = "Segundos de espera entre dos intentos de polling del worker."
  type        = number
}

variable "http_timeout_seconds" {
  description = "Timeout (segundos) de cada petición de polling a TrueNative."
  type        = number
}

variable "max_receive_count" {
  description = "Recibidos máximos antes del redrive a la dead letter queue; debe espejar el max_receive_count de la pila 5_sqs."
  type        = number
  default     = 5
}

variable "lambda_timeout_seconds" {
  description = "Timeout (segundos) de la función Lambda; debe cubrir el peor caso del polling acotado."
  type        = number
}

variable "lambda_memory_mb" {
  description = "Memoria (MB) asignada a la función Lambda."
  type        = number
}

variable "db_username" {
  description = "Unused in this stack; declared only because the course evaluation workflow always passes it via -var."
  type        = string
  sensitive   = true
  default     = null
}

variable "db_password" {
  description = "Unused in this stack; declared only because the course evaluation workflow always passes it via -var."
  type        = string
  sensitive   = true
  default     = null
}
