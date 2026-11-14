# Alexandria-API

## Propósito
Esta API RESTful foi desenvolvida para o gerenciamento ágil do acervo de uma biblioteca e seus processos de empréstimo. O objetivo principal é digitalizar e automatizar o controle de livros, a gestão de cadastros e o rastreamento do ciclo de vida das retiradas e devoluções. O público-alvo inclui bibliotecários e administradores do sistema que necessitam de uma interface centralizada e confiável para manter o acervo atualizado e monitorar as pendências.

## Arquitetura de Recursos
A arquitetura foi modelada de forma relacional em torno de quatro entidades principais do domínio:

| Entidade | Caminho | Descrição |
| --- | --- | --- |
| Livros | /api/v1/lib/acervo | Gerencia o catálogo da biblioteca, incluindo metadados (ISBN, autor), controle de exemplares, status de conservação e estatísticas de uso. |
| Empréstimos | /api/v1/lib/emprestimos | Registra as transações temporais, unindo livros, usuários (leitores) e os funcionários responsáveis pela operação. |
| Usuários | /api/v1/lib/users/usuarios | Controla os leitores cadastrados e gerencia regras de negócio, como o limite de livros simultâneos disponíveis. |
| Funcionários | /api/v1/lib/users/funcionarios | Mantém os dados da equipe administrativa e operadores do sistema. |

### Equipe Envolvida: 
<pre>Guilherme Assunção Barboza — RA: 2840482423014 / GitHub: guiassuno<br>Julia Roberta da Silva — RA: 2840482423020 / GitHub: liaroberta<br><br>FATEC Ribeirão Preto</pre>
