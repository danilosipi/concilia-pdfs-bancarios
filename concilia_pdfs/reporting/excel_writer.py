import pandas as pd
import logging
from pathlib import Path
from typing import List, Dict
from collections import defaultdict
from decimal import Decimal

from concilia_pdfs.core.models import Transaction
from concilia_pdfs.core.reconciliation import ReconciliationResult

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _to_float(d: Decimal | None) -> float | None:
    """Converte Decimal para float de forma segura."""
    if d is None:
        return None
    return float(d)

def generate_excel_report(
    reconciliation_results: Dict[str, ReconciliationResult],
    all_btg_txs: List[Transaction],
    all_organize_txs: List[Transaction],
    output_dir: str
):
    """
    Gera um relatório Excel para o resultado da reconciliação de cada cartão.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    logging.info(f"Gerando relatórios Excel em: {output_dir}")

    # Agrupa transações brutas por cartão para as planilhas
    btg_by_card = defaultdict(list)
    for tx in all_btg_txs:
        btg_by_card[tx.card_final].append(tx.model_dump())

    organize_by_card = defaultdict(list)
    for tx in all_organize_txs:
        organize_by_card[tx.card_final].append(tx.model_dump())

    for card_final, result in reconciliation_results.items():
        report_path = output_path / f"{card_final}_conciliacao.xlsx"
        logging.info(f"Gerando relatório para o cartão {card_final} em: {report_path}")

        with pd.ExcelWriter(report_path, engine='openpyxl') as writer:
            # 1. Planilha btg_normalizado
            if card_final in btg_by_card:
                df_btg = pd.DataFrame(btg_by_card[card_final])
                df_btg['amount'] = pd.to_numeric(df_btg['amount'])
                df_btg['foreign_amount'] = pd.to_numeric(df_btg['foreign_amount'])
                df_btg.to_excel(writer, sheet_name='btg_normalizado', index=False)

            # 2. Planilha organize_normalizado
            if card_final in organize_by_card:
                df_org = pd.DataFrame(organize_by_card[card_final])
                df_org['amount'] = pd.to_numeric(df_org['amount'])
                df_org.to_excel(writer, sheet_name='organize_normalizado', index=False)

            # 3. Planilha comparativo
            comp_data = []
            for btg_tx, org_tx, score in result.exact_matches:
                comp_data.append({
                    "status": "CORRESPONDÊNCIA EXATA", "btg_date": btg_tx.tx_date, "btg_desc": btg_tx.description_raw,
                    "btg_amount": _to_float(btg_tx.amount), "org_date": org_tx.tx_date, "org_desc": org_tx.description_raw,
                    "org_amount": _to_float(org_tx.amount), "similarity": score, "diff_amount": 0.0
                })
            for btg_tx, org_tx, score, diff in result.possible_divergences:
                 comp_data.append({
                    "status": "POSSÍVEL DIVERGÊNCIA", "btg_date": btg_tx.tx_date, "btg_desc": btg_tx.description_raw,
                    "btg_amount": _to_float(btg_tx.amount), "org_date": org_tx.tx_date, "org_desc": org_tx.description_raw,
                    "org_amount": _to_float(org_tx.amount), "similarity": score, "diff_amount": _to_float(diff)
                })
            
            df_comp = pd.DataFrame(comp_data)
            # Adiciona transações faltantes à planilha de comparação para uma visão completa
            missing_rows = []
            for btx_tx in result.missing_in_organize:
                missing_rows.append({
                    "status": "FALTANDO NO ORGANIZE", "btg_date": btx_tx.tx_date, "btg_desc": btx_tx.description_raw,
                    "btg_amount": _to_float(btx_tx.amount)
                })
            df_comp = pd.concat([df_comp, pd.DataFrame(missing_rows)], ignore_index=True)
            df_comp.to_excel(writer, sheet_name='comparativo', index=False)

            # 4. Planilha faltantes_no_organize
            missing_data = [tx.model_dump() for tx in result.missing_in_organize]
            if missing_data:
                df_missing = pd.DataFrame(missing_data)
                df_missing['amount'] = pd.to_numeric(df_missing['amount'])
                df_missing.to_excel(writer, sheet_name='faltantes_no_organize', index=False)
            
            # (Opcional) Planilha extra_no_organize
            extra_data = [tx.model_dump() for tx in result.extra_in_organize]
            if extra_data:
                df_extra = pd.DataFrame(extra_data)
                df_extra['amount'] = pd.to_numeric(df_extra['amount'])
                df_extra.to_excel(writer, sheet_name='extra_no_organize', index=False)

            # 5. Planilha resumo
            sum_btg = sum(Decimal(t['amount']) for t in btg_by_card.get(card_final, []))
            sum_org = sum(Decimal(t['amount']) for t in organize_by_card.get(card_final, []))
            
            summary = {
                "Total de Lançamentos BTG": len(btg_by_card.get(card_final, [])),
                "Total de Lançamentos Organize": len(organize_by_card.get(card_final, [])),
                "Correspondências Exatas": len(result.exact_matches),
                "Possíveis Divergências": len(result.possible_divergences),
                "Faltando no Organize": len(result.missing_in_organize),
                "Sobra no Organize": len(result.extra_in_organize),
                "Soma dos Valores BTG": _to_float(sum_btg),
                "Soma dos Valores Organize (Normalizado)": _to_float(sum_org),
                "Diferença (BTG - Organize)": _to_float(sum_btg - sum_org)
            }
            df_summary = pd.DataFrame.from_dict(summary, orient='index', columns=['Valor'])
            df_summary.to_excel(writer, sheet_name='resumo')

    logging.info("Geração de todos os relatórios Excel finalizada.")


if __name__ == '__main__':
    # Exemplo de uso
    print("Módulo de geração de relatórios Excel carregado.")
    # Em um cenário real, você criaria objetos ReconciliationResult simulados aqui para teste.
