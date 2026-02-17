# concilia_pdfs/core/reconciliation.py
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import List, Dict
import logging

from rapidfuzz import fuzz
from pydantic import BaseModel, Field

from concilia_pdfs.core.models import Transaction

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

SIMILARITY_THRESHOLD = 70  # só para desempate
Q = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(Q)


class ReconciliationResult(BaseModel):
    card_final: str
    missing_in_organize: List[Transaction] = Field(default_factory=list)  # INCLUIR
    extra_in_organize: List[Transaction] = Field(default_factory=list)    # EXCLUIR


def reconcile_transactions(
    btg_txs: List[Transaction],
    org_txs: List[Transaction],
) -> Dict[str, ReconciliationResult]:
    """
    Match principal por VALOR, tolerante a inversão de sinal.
    Garante que NÃO vai marcar INCLUIR se existir no Organize (mesmo valor),
    mesmo que o parser tenha invertido sinal diferente.
    """

    btg_by_card = defaultdict(list)
    org_by_card = defaultdict(list)

    for tx in btg_txs:
        btg_by_card[tx.card_final].append(tx)

    for tx in org_txs:
        org_by_card[tx.card_final].append(tx)

    results: Dict[str, ReconciliationResult] = {}

    for card_final in sorted(set(btg_by_card.keys()) | set(org_by_card.keys())):
        btg = btg_by_card.get(card_final, [])
        org = org_by_card.get(card_final, [])

        # Index do Organize por valor quantizado
        org_index = defaultdict(list)
        for o in org:
            org_index[_q(o.amount)].append(o)

        used_org_ids = set()
        missing_in_organize: List[Transaction] = []

        for b in btg:
            bq = _q(b.amount)

            # tentativa 1: mesmo valor
            candidates = [c for c in org_index.get(bq, []) if id(c) not in used_org_ids]

            # tentativa 2: valor com sinal invertido (caso o parser tenha sinal divergente)
            if not candidates:
                candidates = [c for c in org_index.get(_q(-bq), []) if id(c) not in used_org_ids]

            # tentativa 3: absoluto (último recurso)
            if not candidates:
                abs_key = _q(abs(bq))
                pool = []
                pool.extend(org_index.get(abs_key, []))
                pool.extend(org_index.get(_q(-abs_key), []))
                candidates = [c for c in pool if id(c) not in used_org_ids]

            if not candidates:
                missing_in_organize.append(b)
                continue

            # Desempate: data mais próxima, depois maior similaridade
            best = None
            best_tuple = None

            for c in candidates:
                date_diff = abs((b.tx_date - c.tx_date).days) if (b.tx_date and c.tx_date) else 9999
                sim = fuzz.ratio(b.description_norm, c.description_norm) if (b.description_norm and c.description_norm) else 0
                tup = (date_diff, -sim)
                if best_tuple is None or tup < best_tuple:
                    best_tuple = tup
                    best = c

            used_org_ids.add(id(best))

        extra_in_organize = [o for o in org if id(o) not in used_org_ids]

        results[card_final] = ReconciliationResult(
            card_final=card_final,
            missing_in_organize=missing_in_organize,
            extra_in_organize=extra_in_organize,
        )

    return results
