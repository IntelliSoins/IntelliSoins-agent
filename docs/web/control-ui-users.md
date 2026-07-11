# IntelliSoins Control UI — comptes opérateur et MFA

Cette note décrit la création du premier compte pharmacien pour l'interface Control UI avec authentification MFA (TOTP).

## Prérequis

- IntelliSoins installé sur le poste ou serveur qui héberge le connecteur.
- Accès shell sur la machine du connecteur.

## Créer le premier compte

Sur l'hôte du connecteur :

```bash
intellisoins doctor --create-control-ui-user
```

Le flux interactif demande :

1. **Nom d'utilisateur** — identifiant de connexion (ex. `admin`, `officine-centre`).
2. **Mot de passe** — minimum 8 caractères.
3. **MFA TOTP** — option pour générer un secret et l'ajouter à une application d'authentification (Google Authenticator, Authy, etc.).
4. **Code de confirmation** — saisir un code à 6 chiffres pour activer le MFA.

À la fin, `gateway.auth.mode` est positionné sur `users` dans `openclaw.json`.

### Mode non interactif

```bash
intellisoins doctor --create-control-ui-user --yes --non-interactive
```

En non interactif, le MFA n'est pas confirmé automatiquement. Relancez doctor en interactif pour finaliser l'inscription MFA.

## Connexion Control UI

L'écran de connexion affiche uniquement :

- Nom d'utilisateur
- Mot de passe
- Code MFA (6 chiffres)

Les paramètres avancés (URL WebSocket, jeton automation) restent disponibles sous **Paramètres avancés**.

## Appairage appareil

Après authentification utilisateur, l'appairage navigateur reste requis pour les nouveaux postes (comportement inchangé). Approuvez l'appareil depuis le connecteur :

```bash
intellisoins devices list
intellisoins devices approve <requestId>
```

## Automation / CLI

Le mode `users` conserve la possibilité d'utiliser `gateway.auth.token` pour les clients automation qui envoient un jeton partagé dans `ConnectParams.auth.token`.

## Dépannage

| Symptôme           | Action                                              |
| ------------------ | --------------------------------------------------- |
| Aucun compte       | `intellisoins doctor --create-control-ui-user`      |
| MFA requis         | Saisir le code à 6 chiffres de l'application TOTP   |
| Code MFA refusé    | Vérifier l'heure système du téléphone et du serveur |
| Trop de tentatives | Attendre la fin du verrouillage (rate limit)        |

Documentation publique : <https://docs.openclaw.ai/web/control-ui-users>
