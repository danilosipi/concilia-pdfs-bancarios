from collections import defaultdict
from typing import List, Dict, Tuple
import logging
from decimal import Decimal

from rapidfuzz import fuzz
from pydantic import BaseModel, Field

from concilia_pdfs.core.models import Transaction

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SIMILARITY_THRESHOLD = 90  # 90% similarity for description matching

def amount_equal(a: Decimal, b: Decimal, tol: Decimal = Decimal("0.01")) -> bool:
    """Verifica se dois valores Decimais são iguais dentro de uma dada tolerância."""
    return abs(a - b) <= tol

class ReconciliationResult(BaseModel):
    """Armazena os resultados da reconciliação para um único cartão."""
    card_final: str
    exact_matches: List[Tuple[Transaction, Transaction, float]] = Field(default_factory=list)
    possible_divergences: List[Tuple[Transaction, Transaction, float, float]] = Field(default_factory=list)
    missing_in_organize: List[Transaction] = Field(default_factory=list)
    extra_in_organize: List[Transaction] = Field(default_factory=list)

def reconcile_transactions(
    btg_transactions: List[Transaction],
    organize_transactions: List[Transaction]
) -> Dict[str, ReconciliationResult]:
    """
    Reconcilia as transações das fontes BTG e Organize.
    """
    logging.info(f"Iniciando processo de reconciliação para {len(btg_transactions)} transações BTG e "
                 f"{len(organize_transactions)} transações Organize.")

    # 1. Agrupa as transações por cartão
    btg_by_card = defaultdict(list)
    for tx in btg_transactions:
        btg_by_card[tx.card_final].append(tx)

    organize_by_card = defaultdict(list)
    for tx in organize_transactions:
        organize_by_card[tx.card_final].append(tx)

    all_card_finals = set(btg_by_card.keys()) | set(organize_by_card.keys())
    results: Dict[str, ReconciliationResult] = {}

    # 2. Para cada cartão, realiza a reconciliação
    for card_final in all_card_finals:
        logging.info(f"Reconciliando transações para o cartão de final: {card_final}")
        result = ReconciliationResult(card_final=card_final)
        
        btg_txs = btg_by_card.get(card_final, [])
        organize_txs = organize_by_card.get(card_final, [])
        
        unmatched_organize_indices = set(range(len(organize_txs)))

        for btg_tx in btg_txs:
            best_match = None
            highest_score = 0
            best_match_idx = -1
            best_diff_abs = None

            # Encontra a melhor correspondência potencial na lista do Organize
            for i, org_tx in enumerate(organize_txs):
                if i not in unmatched_organize_indices:
                    continue

                if btg_tx.tx_date != org_tx.tx_date:
                    continue

                score = fuzz.ratio(btg_tx.description_norm, org_tx.description_norm)
                if score < SIMILARITY_THRESHOLD:
                    continue

                # Prioriza valor: exato (dentro da tolerância) > mais próximo > similaridade
                diff_abs = abs(btg_tx.amount - org_tx.amount)

                if best_match is None:
                    best_match = org_tx
                    best_match_idx = i
                    highest_score = score
                    best_diff_abs = diff_abs
                    continue

                # ranking: (amount_equal desc, diff_abs asc, score desc)
                best_equal = amount_equal(btg_tx.amount, best_match.amount)
                cur_equal = amount_equal(btg_tx.amount, org_tx.amount)

                if cur_equal and not best_equal:
                    best_match = org_tx
                    best_match_idx = i
                    highest_score = score
                    best_diff_abs = diff_abs
                    continue

                if cur_equal == best_equal:
                    if diff_abs < best_diff_abs:
                        best_match = org_tx
                        best_match_idx = i
                        highest_score = score
                        best_diff_abs = diff_abs
                        continue
                    if diff_abs == best_diff_abs and score > highest_score:
                        best_match = org_tx
                        best_match_idx = i
                        highest_score = score
                        best_diff_abs = diff_abs
                        continue

            
            # 3. Categoriza a correspondência
            if best_match and highest_score >= SIMILARITY_THRESHOLD:
                unmatched_organize_indices.remove(best_match_idx)
                
                # Usa amount_equal para comparação de Decimais
                if amount_equal(btg_tx.amount, best_match.amount):
                    result.exact_matches.append((btg_tx, best_match, highest_score))
                else:
                    diff = btg_tx.amount - best_match.amount
                    result.possible_divergences.append((btg_tx, best_match, highest_score, diff))
            else:
                # 4. Nenhuma correspondência adequada encontrada
                result.missing_in_organize.append(btg_tx)

        # 5. Identifica transações restantes do Organize como extras
        for i in unmatched_organize_indices:
            result.extra_in_organize.append(organize_txs[i])
            
        results[card_final] = result
        logging.info(f"Finalizada a reconciliação para o cartão {card_final}: "
                     f"{len(result.exact_matches)} correspondências exatas, "
                     f"{len(result.possible_divergences)} divergências, "
                     f"{len(result.missing_in_organize)} faltantes, "
                     f"{len(result.extra_in_organize)} extras.")

    logging.info("Processo de reconciliação finalizado.")
    return results

if __name__ == '__main__':
    # Exemplo de uso para demonstração
    print("Módulo de reconciliação carregado.")
    # Em um cenário real, você criaria objetos Transaction simulados aqui para teste.
