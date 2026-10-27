# Modèle de données PostgreSQL — API de chatbot IA

## Table `conversations`

| Colonne | Type PostgreSQL | Rôle |
|---|---|---|
| `id` | `UUID` | Clé primaire |
| `title` | `VARCHAR(255)` | Titre facultatif de la conversation |
| `created_at` | `TIMESTAMPTZ` | Date de création |
| `updated_at` | `TIMESTAMPTZ` | Date de dernière modification |

## Table `messages`

| Colonne | Type PostgreSQL | Rôle |
|---|---|---|
| `id` | `UUID` | Clé primaire |
| `conversation_id` | `UUID` | Clé étrangère vers `conversations.id` |
| `role` | `VARCHAR(20)` | Rôle de l'auteur : `user` ou `assistant` |
| `content` | `TEXT` | Contenu du message |
| `created_at` | `TIMESTAMPTZ` | Date de création du message |

## Relation entre les tables

Une conversation peut contenir plusieurs messages. Chaque message appartient à une seule conversation.

- `conversations.id` : clé primaire.
- `messages.conversation_id` : clé étrangère vers `conversations.id`.
