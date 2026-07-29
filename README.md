# 💰 Controle Financeiro

![Status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow)
![Python](https://img.shields.io/badge/Python-3.x-blue)
![Flask](https://img.shields.io/badge/Flask-Framework-black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-blue)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5-purple)

Sistema web para gerenciamento financeiro pessoal desenvolvido em **Python + Flask + PostgreSQL**, com foco em organização financeira, controle de despesas, receitas e cartões de crédito.

> **Status do projeto:** 🚧 Em evolução — atualmente passando por um processo de redesign completo da interface mantendo 100% da lógica de negócio existente.

---

## 📑 Índice

- [Visão Geral](#-visão-geral)
- [Tecnologias](#-tecnologias)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Como Executar](#-como-executar)
- [Documentação](#-documentação)
- [Redesign da Interface](#-redesign-da-interface)
- [Princípios do Projeto](#-princípios-do-projeto)
- [Versionamento](#-versionamento)
- [Próximos Passos](#-próximos-passos)

---

# 📸 Visão Geral

O sistema permite acompanhar a situação financeira através de um dashboard intuitivo e gerenciar todas as movimentações financeiras em um único lugar.

## Objetivo

O objetivo do **Controle Financeiro** é fornecer uma plataforma simples e intuitiva para gerenciamento financeiro pessoal, permitindo acompanhar receitas, despesas, cartões de crédito e indicadores financeiros de forma organizada.

Além do uso pessoal, o projeto também serve como ambiente de estudo e evolução em desenvolvimento web utilizando Flask e PostgreSQL.

## Funcionalidades

- 📊 Dashboard Financeiro
- 💵 Controle de Receitas e Despesas
- 💳 Cartões de Crédito
- 🧾 Controle de Faturas
- 🏦 Contas Bancárias
- 🏷 Categorias
- 💰 Meios de Pagamento
- 📈 Relatórios
- 🔄 Transferências entre Contas

---

# 🛠 Tecnologias

## Backend

- Python
- Flask
- SQLAlchemy
- PostgreSQL

## Frontend

- HTML5
- CSS3
- Bootstrap
- JavaScript

---

# 🏗 Arquitetura

O projeto segue uma arquitetura baseada em Flask, separando responsabilidades entre:

- Models
- Rotas
- Templates
- Arquivos estáticos
- Serviços
- Utilitários

Essa organização facilita manutenção, testes e evolução do sistema.

# 📁 Estrutura do Projeto

```
Controle_Financeiro/
│
├── app/
│   ├── routes/
│   ├── services/
│   ├── static/
│   ├── templates/
│   └── utils/
│
├── docs/
├── migrations/
├── tests/
├── tools/
│
├── run.py
├── config.py
├── requirements.txt
└── README.md
```

---

# 🚀 Como executar

## 1. Clonar o projeto

```bash
git clone <repositorio>
```

## 2. Criar ambiente virtual

Windows

```bash
python -m venv .venv
```

Ativar

```bash
.venv\Scripts\activate
```

## 3. Instalar dependências

```bash
pip install -r requirements.txt
```

## 4. Configurar as variáveis de ambiente

Crie um arquivo `.env` conforme sua configuração local.

## 5. Executar

```bash
python run.py
```

---

# 📚 Documentação

Toda a documentação técnica do projeto está localizada na pasta `docs/`.

Este projeto possui documentação complementar:

| Arquivo                 | Descrição                     |
| ----------------------- | ----------------------------- |
| `docs/VISION.md`        | Objetivos do sistema          |
| `docs/Roadmap.md`       | Evolução planejada            |
| `docs/DESIGN_SYSTEM.md` | Documentação do Design System |
| `docs/estilo.md`        | Guia visual                   |

---

# 🎨 Redesign da Interface

O frontend está sendo modernizado com os seguintes objetivos:

- Design System reutilizável
- Layout responsivo
- Melhor experiência do usuário
- Acessibilidade
- Componentização
- Preservação total da lógica de negócio

Até o momento foram concluídas:

- ✅ Arquitetura CSS
- ✅ Layout Base
- ✅ Sidebar
- ✅ Topbar
- ✅ Dashboard
- ✅ Telas principais
- 🚧 Telas auxiliares em andamento

---

# 🔒 Princípios do Projeto

Durante o redesign:

- Nenhuma regra de negócio é alterada.
- Nenhuma rota Flask é modificada.
- Nenhuma Model é alterada.
- Nenhuma Migration é modificada.
- O banco de dados permanece compatível.

---

# 📝 Versionamento

O projeto utiliza **Git** para controle de versão.

Fluxo adotado:

```
main
 │
 ├── Commits estáveis
 │
 └── Branches de desenvolvimento
```

---

# 📌 Próximos Passos

- Finalizar redesign das telas restantes
- Revisão completa (QA)
- Melhorias de acessibilidade
- Otimizações de CSS
- Revisão de responsividade

---

# 🤝 Contribuição

Este projeto está em desenvolvimento contínuo.

Sugestões e melhorias são bem-vindas através de Issues ou Pull Requests.

---

# 👨‍💻 Autor

Projeto desenvolvido e mantido por **Fernando Lopes**.
