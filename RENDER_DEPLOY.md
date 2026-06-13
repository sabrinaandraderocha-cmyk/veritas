# Publicação do Veritas no Render

## Opção recomendada: Blueprint

1. Crie um repositório no GitHub e envie todos os arquivos deste projeto.
2. Entre no painel do Render.
3. Clique em **New +** e depois em **Blueprint**.
4. Conecte o repositório do Veritas.
5. O Render localizará o arquivo `render.yaml`.
6. Quando solicitado, informe a variável secreta `SERPAPI_KEY`.
7. Confirme a criação do serviço.

O aplicativo será disponibilizado em um endereço semelhante a:

```text
https://veritas-app.onrender.com
```

O nome final depende da disponibilidade do subdomínio.

## Opção manual: Web Service

1. Clique em **New + > Web Service**.
2. Conecte o repositório do GitHub.
3. Selecione **Docker** como runtime.
4. Escolha o plano desejado.
5. Em **Environment**, adicione:

```text
SERPAPI_KEY = sua_chave
```

6. Em **Health Check Path**, informe:

```text
/_stcore/health
```

7. Crie o serviço.

## Atualizações

Quando o serviço estiver conectado ao GitHub, alterações enviadas à branch configurada podem gerar uma nova implantação automática.

## Observações importantes

- Não envie `.streamlit/secrets.toml` ou arquivos `.env` ao GitHub.
- A biblioteca atual é temporária e fica apenas na sessão do Streamlit.
- Reinicializações do serviço apagam arquivos gravados apenas no sistema local do contêiner.
- A SerpAPI é opcional. Sem a chave, a comparação local e a análise linguística continuam disponíveis.
- No plano gratuito, o serviço pode apresentar limitações de disponibilidade e recursos.
