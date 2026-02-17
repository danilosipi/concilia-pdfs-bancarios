# concilia_pdfs/__main__.py
import argparse
import logging
from pathlib import Path
import sys
import os
import getpass

sys.path.insert(0, str(Path(__file__).parent.parent))

from concilia_pdfs.parsers.btg_parser import parse_btg_pdf
from concilia_pdfs.parsers.organize_parser import parse_organize_pdf
from concilia_pdfs.core.reconciliation import reconcile_transactions
from concilia_pdfs.reporting.excel_writer import generate_excel_report


def _resolve_pdf_password(args) -> str | None:
    if args.pdf_password:
        return args.pdf_password
    env_pwd = os.getenv("CONCILIA_PDF_PASSWORD")
    if env_pwd:
        return env_pwd
    try:
        pwd = getpass.getpass("PDF protegido. Digite a senha (ENTER para tentar sem senha): ").strip()
        return pwd if pwd else None
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Reconcilia extratos BTG x Organize.")
    parser.add_argument("--pdf_password", type=str, default=None)
    parser.add_argument("--btg", type=str, required=True)
    parser.add_argument("--organize_dir", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")

    logging.info("--- Iniciando Processo de Reconciliação ---")

    pdf_password = _resolve_pdf_password(args)

    btg_file = Path(args.btg)
    if not btg_file.is_file():
        logging.error(f"Arquivo BTG não encontrado: {btg_file}")
        return

    all_btg_txs = list(parse_btg_pdf(str(btg_file), pdf_password=pdf_password))
    logging.info(f"BTG carregado: {len(all_btg_txs)} transações")

    organize_dir = Path(args.organize_dir)
    if not organize_dir.is_dir():
        logging.error(f"Diretório do Organize não encontrado: {organize_dir}")
        return

    # BTG por cartão
    btg_by_card = {}
    for tx in all_btg_txs:
        btg_by_card.setdefault(tx.card_final, []).append(tx)

    reconciliation_results_all = {}

    for card_final in sorted(btg_by_card.keys()):
        candidate_a = organize_dir / f"{card_final}.pdf"
        candidate_b = organize_dir / f"final_{card_final}.pdf"

        org_file = candidate_a if candidate_a.is_file() else (candidate_b if candidate_b.is_file() else None)

        if not org_file:
            logging.warning(
                f"[SKIP] Cartão {card_final}: PDF do Organize não encontrado "
                f"(esperado {candidate_a.name} ou {candidate_b.name}). NÃO vou gerar diferenças para este cartão."
            )
            continue

        org_txs = list(parse_organize_pdf(str(org_file), pdf_password=pdf_password))
        logging.info(f"[Organize] Cartão {card_final}: {len(org_txs)} transações (arquivo={org_file.name})")

        # concilia SOMENTE este cartão
        btg_txs = btg_by_card[card_final]
        rec_one = reconcile_transactions(btg_txs, org_txs)
        # reconcile_transactions retorna dict; pegamos a chave do próprio cartão
        if card_final in rec_one:
            reconciliation_results_all[card_final] = rec_one[card_final]

    generate_excel_report(reconciliation_results_all, all_btg_txs, [], args.out)

    logging.info("--- Processo Finalizado ---")


if __name__ == "__main__":
    main()
