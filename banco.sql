-- banco.sql — CENÁRIO DE EXEMPLO: CAMPEONATO INTERCLASSE
-- Cada grupo troca este arquivo pelo banco do seu próprio cenário.
-- Depois de executar, o nome do banco (interclasse) vai no CONFIG_BANCO do app.py.
--
-- Relação: um time tem vários jogadores (1:N).
-- A chave estrangeira fica no lado N: jogadores.time_id aponta para times.id.

CREATE DATABASE IF NOT EXISTS interclasse CHARACTER SET utf8mb4;
USE interclasse;

CREATE TABLE IF NOT EXISTS times (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(60) NOT NULL,
    turma VARCHAR(20) NOT NULL,
    cor_uniforme VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS jogadores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(80) NOT NULL,
    numero_camisa INT,
    posicao ENUM('Goleiro', 'Defesa', 'Meio-campo', 'Ataque'),
    time_id INT NOT NULL,
    FOREIGN KEY (time_id) REFERENCES times(id)
);

-- Alguns dados para a página já abrir com conteúdo (rode só uma vez).
INSERT INTO times (nome, turma, cor_uniforme) VALUES
    ('Furacão DS', '2º ano A', 'Azul'),
    ('Unidos do Código', '2º ano B', 'Verde');

INSERT INTO jogadores (nome, numero_camisa, posicao, time_id) VALUES
    ('Ana Clara', 1, 'Goleiro', 1),
    ('Lucas Rocha', 10, 'Meio-campo', 1),
    ('Bia Martins', 9, 'Ataque', 2),
    ('Pedro Henrique', 4, 'Defesa', 2);
