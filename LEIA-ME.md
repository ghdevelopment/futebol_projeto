# Servidor do projeto — Python + MySQL + HTML + CSS

O `app.py` já está pronto e funciona com **qualquer cenário**. O grupo não precisa escrever Python: o trabalho de vocês é o **banco** (SQL), as **páginas** (HTML) e a **aparência** (CSS).

```
servidor-projeto/
├── app.py          ← servidor pronto (só muda o CONFIG_BANCO)
├── banco.sql       ← CREATE DATABASE e CREATE TABLE do grupo
├── requirements.txt
├── templates/      ← páginas HTML do grupo
│   └── index.html  ← primeira página do site (endereço /)
└── static/         ← CSS e imagens
    └── estilo.css
```

## 1. Preparar (uma vez por computador)

No terminal, dentro da pasta do projeto:

```
pip install -r requirements.txt
```

## 2. Criar o banco do grupo

1. Abra o `banco.sql` no MySQL Workbench (ou phpMyAdmin).
2. Troque o exemplo pelas tabelas do cenário do grupo.
3. Execute o arquivo inteiro.

> Toda tabela precisa de uma chave primária, de preferência assim: `id INT AUTO_INCREMENT PRIMARY KEY`. Sem ela não dá para editar nem excluir.

## 3. Configurar a conexão

No `app.py`, ajuste o `CONFIG_BANCO`: usuário, senha e **o nome do banco do grupo** em `database`.

## 4. Rodar

```
python app.py
```

Abra no navegador: **http://127.0.0.1:5000**

- `/painel` mostra todas as tabelas do banco, com um formulário de teste para cada uma **e o código HTML pronto para copiar**.
- Para parar o servidor: `Ctrl + C` no terminal.

## 5. Criar páginas

Cada arquivo na pasta `templates` vira um endereço:

| Arquivo                     | Endereço       | Link no HTML                      |
| --------------------------- | -------------- | --------------------------------- |
| `templates/index.html`      | `/`            | `<a href="/">Início</a>`          |
| `templates/cadastro.html`   | `/cadastro`    | `<a href="/cadastro">Cadastro</a>`|
| `templates/sobre.html`      | `/sobre`       | `<a href="/sobre">Sobre</a>`      |

CSS e imagens ficam na pasta `static`:

```html
<link rel="stylesheet" href="/static/estilo.css">
<img src="/static/logo.png" alt="Logo do grupo">
```

## 6. Gravar dados (INSERT)

```html
<form method="post" action="/salvar/jogadores">
    <input type="text" name="nome">
    <input type="number" name="numero_camisa">
    <button type="submit">Salvar</button>
</form>
```

Três regras:

1. `method="post"`
2. `action="/salvar/NOME_DA_TABELA"`
3. o `name` de cada campo é **igual ao nome da coluna** no banco

Campos deixados em branco usam o valor padrão do banco (ou `NULL`). Números com vírgula (`2,50`) são aceitos.

## 7. Mostrar dados (SELECT)

Todas as linhas de uma tabela:

```html
{% for jogador in listar("jogadores") %}
    <p>{{ jogador.nome }} — camisa {{ jogador.numero_camisa }}</p>
{% endfor %}
```

Em ordem: `listar("jogadores", ordem="nome")` ou `ordem="nome desc"`.

Qualquer SELECT, inclusive com JOIN:

```html
{% for j in consultar("SELECT j.nome, t.nome AS time FROM jogadores j JOIN times t ON t.id = j.time_id") %}
    <p>{{ j.nome }} joga no {{ j.time }}</p>
{% endfor %}
```

> Quando duas colunas têm o mesmo nome (`j.nome` e `t.nome`), dê um apelido com `AS`.

SELECT com valor vindo de fora: use `%s`, igual no Python.

```html
{% for j in consultar("SELECT * FROM jogadores WHERE time_id = %s", request.args.time) %}
```

Formatação brasileira:

- `{{ produto.preco | dinheiro }}` → `R$ 1.234,50`
- `{{ partida.data | data_br }}` → `26/10/2026`

## 8. Editar (UPDATE)

1. Na lista, um link com o id: `<a href="/editar_time?id={{ time.id }}">Editar</a>`
2. Na página `editar_time.html`, busque a linha e preencha o formulário com `value`:

```html
{% set time = buscar("times", request.args.id) %}

<form method="post" action="/atualizar/times/{{ time.id }}">
    <input type="hidden" name="_voltar" value="/">
    <input type="text" name="nome" value="{{ time.nome }}">
    <button type="submit">Salvar alterações</button>
</form>
```

O campo `_voltar` diz para qual página ir depois de salvar. Sem ele, o servidor volta para a página do formulário.

## 9. Excluir (DELETE)

```html
<form method="post" action="/excluir/times/{{ time.id }}">
    <button type="submit">Excluir</button>
</form>
```

## 10. Quando der erro

O servidor mostra uma página explicando o problema em português e como resolver. Os mais comuns:

| Mensagem                                   | O que fazer                                                      |
| ------------------------------------------ | ---------------------------------------------------------------- |
| Não foi possível conectar ao MySQL         | Ligue o MySQL (no XAMPP: Start) e confira `host` e `port`        |
| O MySQL recusou o usuário ou a senha       | Confira `user` e `password` no `CONFIG_BANCO`                    |
| O banco informado não existe               | Rode o `banco.sql` ou corrija `database`                         |
| A tabela não tem a coluna 'x'              | O `name` do campo está diferente do nome da coluna               |
| O campo 'x' é obrigatório                  | A coluna é `NOT NULL`: o formulário precisa enviar esse campo     |
| O valor escolhido não existe na tabela ligada | Cadastre primeiro o registro "pai" (ex.: o time antes do jogador) |
| Este registro não pode ser excluído        | Outros registros dependem dele: exclua os "filhos" primeiro       |
| Não existe o arquivo templates/x.html      | Crie o arquivo ou corrija o link                                 |

Erros de digitação no HTML (por exemplo, esquecer um `{% endfor %}`) aparecem numa página com o número da linha do problema.

## O que este servidor não faz

Login com senha e envio de arquivos (upload de fotos). Se o projeto do grupo precisar disso, converse com o professor.
