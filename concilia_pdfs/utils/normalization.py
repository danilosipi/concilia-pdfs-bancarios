import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Optional

import unidecode

MONTH_MAP = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12
}

def normalize_text(text: str) -> str:
    """
    Normaliza uma string através de:
    1. Remoção de acentos.
    2. Conversão para minúsculas.
    3. Remoção de caracteres não alfanuméricos (exceto espaços).
    4. Redução de múltiplos espaços para um só.
    5. Remoção de espaços em branco das extremidades.
    """
    if not isinstance(text, str):
        return ""
    text = unidecode.unidecode(text)
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_brl_value(value_str: str) -> Optional[Decimal]:
    """
    Analisa uma string representando um valor em Real (BRL) para um Decimal.
    Lida com formatos como '1.234,56' ou '1234.56'.
    """
    if not isinstance(value_str, str):
        return None
    cleaned_str = value_str.replace("R$", "").strip()
    if re.search(r',\d{2}$', cleaned_str):
        cleaned_str = cleaned_str.replace('.', '').replace(',', '.')
    else:
        cleaned_str = cleaned_str.replace(',', '')
    try:
        if not cleaned_str:
            return None
        return Decimal(cleaned_str)
    except (InvalidOperation, ValueError):
        return None


def parse_date(date_str: str, year: Optional[int] = None) -> Optional[date]:
    """
    Analisa uma string de data em múltiplos formatos possíveis.
    - DD/MM/YYYY
    - DD/MM/YY
    - DD Mon (ex: '20 Fev')
    """
    if not isinstance(date_str, str):
        return None
    
    cleaned_str = date_str.strip()

    # Tenta o formato DD/MM/YYYY
    try:
        return datetime.strptime(cleaned_str, '%d/%m/%Y').date()
    except ValueError:
        pass

    # Tenta o formato DD/MM/YY
    try:
        return datetime.strptime(cleaned_str, '%d/%m/%y').date()
    except ValueError:
        pass
    
    # Tenta o formato 'DD Mon'
    try:
        current_year = year if year else date.today().year
        day_str, month_abbr = cleaned_str.split()
        day = int(day_str)
        month_abbr_clean = month_abbr.lower().strip('.')
        month = MONTH_MAP.get(month_abbr_clean)
        if month:
            return date(current_year, month, day)
    except (ValueError, AttributeError, KeyError):
        pass

    return None


def parse_date_d_mon(date_str: str, year: Optional[int] = None) -> Optional[date]:
    """
    Analisador legado para o formato 'DD Mês'. Prefira o novo `parse_date`.
    """
    return parse_date(date_str, year)


if __name__ == '__main__':
    # Exemplo de Uso
    print(f"'Pagamento' -> '{normalize_text('Pagamento')}'")
    print(f"'R$ 1.234,56' -> {parse_brl_value('R$ 1.234,56')}")
    print(f"'1,000' -> {parse_brl_value('1,000')}")
    print(f"'-55,90' -> {parse_brl_value('-55,90')}")
    print(f"'20 Fev' -> {parse_date('20 Fev')}")
    print(f"'25/12/2023' -> {parse_date('25/12/2023')}")
    print(f"'01/01/24' -> {parse_date('01/01/24')}")
    print(f"Data Inválida -> {parse_date('invalid')}")


