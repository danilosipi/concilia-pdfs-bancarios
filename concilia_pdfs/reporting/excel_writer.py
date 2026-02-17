# concilia_pdfs/reporting/excel_writer.py
import logging
from pathlib import Path
from decimal import Decimal
from typing import List, Dict

import pandas as pd

from concilia_pdfs.core.models import Transaction
from concilia_pdfs.core.reconciliation import ReconciliationResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def _to_float(d: Decimal | None) -> float | None:
    return float(d) if d is not None else None


def _tx_to_row(action: str, tx: Transaction) -> dict:
    return {
        "acao": action,  # INCLUIR / EXCLUIR
        "cartao": tx.card_final,
        "data": tx.tx_date,
        "descricao": tx.description_raw,
        "valor_brl": _to_float(tx.amount),
        "fonte": tx.source.value if hasattr(tx.source, "value") else str(tx.source),
        "moeda": getattr(tx, "foreign_currency", None),
        "valor_estrangeiro": _to_float(getattr(tx, "foreign_amount", None)),
    }


def generate_excel_report(
    reconciliation_results: Dict[str, ReconciliationResult],
    all_btg_txs: List[Transaction],          # mantido por compatibilidade
    all_organize_txs: List[Transaction],     # mantido por compatibilidade
    output_dir: str,
):
    """
    Gera Excel SOMENTE com diferenças (nunca inclui itens que bateram).
    Ordena por valor_brl (menor -> maior).
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    total_files = 0

    for card_final, result in reconciliation_results.items():
        rows: list[dict] = []

        for tx in result.missing_in_organize:
            rows.append(_tx_to_row("INCLUIR", tx))

        for tx in result.extra_in_organize:
            rows.append(_tx_to_row("EXCLUIR", tx))

        if not rows:
            logging.info(f"Cartão {card_final}: sem diferenças. Nenhum Excel gerado.")
            continue

        df = pd.DataFrame(rows)

        # Ordenação pedida: menor para maior por valor
        df["valor_ord"] = df["valor_brl"].abs()  # ordena pelo "valor" independente do sinal
        df = df.sort_values(by=["valor_ord", "acao", "data"], ascending=[True, True, True]).drop(columns=["valor_ord"])

        report_path = out_dir / f"{card_final}_diferencas.xlsx"

        with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="diferencas", index=False)

            resumo = pd.DataFrame(
                {
                    "campo": ["cartao", "qtd_incluir", "qtd_excluir"],
                    "valor": [
                        card_final,
                        len(result.missing_in_organize),
                        len(result.extra_in_organize),
                    ],
                }
            )
            resumo.to_excel(writer, sheet_name="resumo", index=False)

        total_files += 1
        logging.info(f"Gerado: {report_path}")

    logging.info(f"Relatórios gerados: {total_files}")
