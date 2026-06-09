---
paths:
  - "**/*.sql"
  - "prisma/**"
  - "**/*.prisma"
  - "**/db.ts"
  - "**/prisma.ts"
  - "scripts/*.sql"
---

# PostgreSQL Display Format

Quand on presente des rows PostgreSQL (transactions, records, schemas),
utiliser un tableau box-drawing groupe par sections logiques:

- Grouper les colonnes par role (identite, montants, FK dimensions, flags, metadata)
- Resoudre TOUTES les FK en noms lisibles (jamais un id brut seul)
- Utiliser `(null)` pour NULL et `(vide)` pour chaine vide
- Sections separees par ├───┼───┤
- Annoter les valeurs remarquables avec `← commentaire`

## Exemple (transaction financiere)

```
┌─────────────────────────┬──────────────────────────────────┐
│ IDENTITE                │                                  │
├─────────────────────────┼──────────────────────────────────┤
│ id                      │ 4327                             │
│ date                    │ 2026-02-02                       │
├─────────────────────────┼──────────────────────────────────┤
│ MONTANTS                │                                  │
├─────────────────────────┼──────────────────────────────────┤
│ debit                   │ 810.12                           │
│ credit                  │ 0.00                             │
├─────────────────────────┼──────────────────────────────────┤
│ DIMENSIONS (FK)         │                                  │
├─────────────────────────┼──────────────────────────────────┤
│ compte                  │ Cheque                           │
│ categorie               │ Hypotheque et loyer              │
├─────────────────────────┼──────────────────────────────────┤
│ FLAGS                   │                                  │
├─────────────────────────┼──────────────────────────────────┤
│ is_duplicate            │ false                            │
│ transaction_type        │ expense  ← valeur inhabituelle   │
└─────────────────────────┴──────────────────────────────────┘
```
