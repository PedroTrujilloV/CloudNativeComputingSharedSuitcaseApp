from enum import Enum


class CardStatus(str, Enum):
    """Card statuses of the CreditCard entity (shared storage contract).

    The values match exactly the enum of the credit_cards_app, the owner
    of the table. The worker only writes the two terminal values;
    POR_VERIFICAR is the state left by the credit cards application while
    the asynchronous verification runs.
    """

    POR_VERIFICAR = "POR_VERIFICAR"
    RECHAZADA = "RECHAZADA"
    APROBADA = "APROBADA"
