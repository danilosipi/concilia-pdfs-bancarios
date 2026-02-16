from datetime import date
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Source(str, Enum):
    """Enum para identificar a origem da transação."""
    BTG = "BTG"
    ORGANIZE = "ORGANIZE"


class Transaction(BaseModel):
    """
    Representa uma única transação financeira, normalizada a partir de uma fonte.
    """
    card_final: str = Field(..., description="Últimos quatro dígitos do cartão.")
    source: Source = Field(..., description="A fonte da transação (ex: BTG, ORGANIZE).")
    tx_date: date = Field(..., description="Data da transação.")
    description_raw: str = Field(..., description="A descrição bruta, inalterada, da fonte.")
    description_norm: str = Field(..., description="Descrição normalizada para correspondência.")
    amount: Decimal = Field(
        ...,
        description="Valor da transação em BRL. Positivo para débito, negativo para crédito."
    )
    currency: str = Field("BRL", description="Moeda do campo 'amount' (sempre BRL).")

    # Campos opcionais para transações internacionais
    foreign_currency: Optional[str] = Field(None, description="Moeda original de uma transação internacional.")
    foreign_amount: Optional[Decimal] = Field(None, description="Valor original na moeda estrangeira.")
    fx_rate_brl: Optional[Decimal] = Field(None, description="A taxa de câmbio aplicada.")
    
    raw_lines: List[str] = Field(default_factory=list, description="Linhas brutas do PDF usadas para construir esta transação, para auditoria.")

    class Config:
        # Permite compatibilidade com modelos ORM, se algum dia usarmos
        from_attributes = True
        # Garante que membros do Enum sejam usados como valores
        use_enum_values = True
        # Proíbe campos extras não definidos no modelo
        extra = "forbid"

    @property
    def amount_abs(self) -> Decimal:
        """Retorna o valor absoluto do montante."""
        return abs(self.amount)
