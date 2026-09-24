aws_region = "us-east-1"
owner      = "pe.trujillo"

queue_name = "grupo33-card-verification"
dead_letter_queue_name = "grupo33-card-verification-dlq"

# Worst case invocation of the worker (5 attempts x 3 s HTTP timeout +
# 4 waits x 2 s) is under 30 s; 45 s leaves margin so a failed invocation
# redelivers the message right after the visibility window.
visibility_timeout_seconds = 45

# Budget before the dead letter queue: 5 receives covers the 30 second
# TrueNative SLA with room for transient failures across redeliveries.
max_receive_count = 5
