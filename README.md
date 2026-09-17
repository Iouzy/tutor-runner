# gradus

Ensina a programar gastando o mínimo de contexto possível — e guarda tudo o que
se passou, para que a aprendizagem possa ser analisada depois.

**Uma sessão de estudo** é tu sentado duas horas. **Uma sessão do Claude** é
descartável: morre ao fim de cada exercício, ou antes disso se o contexto
engordar. O estado durável é o exercício, não a conversa.

## Correr

```bash
python3 -m gradus demo --limpar   # um dia de estudo inteiro, sem modelo e sem rede
python3 -m gradus proximo         # que exercício vem a seguir, e porquê
python3 -m gradus briefing        # o contexto exato que a próxima sessão recebe
python3 -m gradus estado          # regenera ESTADO.md
python3 -m gradus historico       # regenera HISTORICO.md
python3 -m unittest discover -s tests -t .
```

Python 3.11+ (tomllib). **Sem dependências**, por desenho.

## As três camadas

| Camada | Tamanho | Quem a lê |
|---|---|---|
| `briefing` | ~2 KB, com teto verificado | a sessão do Claude |
| `eventos/` + `telemetria/` | KB | as regras, sem modelo |
| `arquivo/` | MB | ninguém, até alguém pedir |

O arquivo só custa zero contexto porque nada o lê. `tests/test_guard.py` falha
se alguma vez entrar na allowlist do montador de briefings.

## Factos e juízos

Tudo o que é contável é contado pelo programa: compilações, o erro exato do
compilador, versões até correr, mensagens antes da primeira linha de código,
KB de contexto. O modelo só declara o que só ele sabe — que fraqueza causou o
erro, se a dúvida era de conceito ou de sintaxe. Um modelo a reconstruir
contagens de memória corrompe o dataset que o projeto existe para construir.

## O escalonador

O próximo exercício é uma função sobre o grafo, não uma opinião: dos nós cujos
pré-requisitos estão todos em `escrito sozinho`, escolhe o que treina mais
fraquezas ativas. Um nó em `automático` decai ao fim de `decaimento_dias` e
volta a aparecer — repetição espaçada, porque esquecer é o modo de falha que
este projeto tem no nome.

Um exercício passado sobe **um** degrau. Só o simulador (dez previsões seguidas
certas) leva um nó a `automático`. Ter commit não é saber.

## Agnóstico

O motor não sabe o que é Java. O curso traz o seu grafo, os seus comandos de
build e o regex que apanha os erros do compilador:

```toml
build = "javac -d out {ficheiro}"
regex_erro = "^(?P<ficheiro>.+):(?P<linha>\\d+): error: (?P<msg>.+)$"
```

Troca por Python ou SQL e nada em `gradus/` muda.

## Estado

O que corre hoje: grafo, escalonador com decaimento, montador de briefing com
orçamento, esquema de eventos com validação, sensores de compilação, arquivo com
redação de segredos, geração de ESTADO.md e HISTORICO.md, e o ciclo de corte e
arranque a frio — tudo exercitado por `gradus demo` com uma sessão falsa.

O que **não** está feito: o lançador real (`claude -p` em sessão fria), o parser
de transcrições a sério, o simulador de previsões, e o render HTML do arquivo.
Nenhuma sessão de modelo foi alguma vez lançada por este código.
