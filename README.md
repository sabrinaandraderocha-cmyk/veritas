# Veritas 1.1

Ferramenta de apoio à análise de similaridade textual e à leitura exploratória de padrões linguísticos.

## Melhorias incorporadas

- remoção das expressões “Original” e “probabilidade de IA”;
- análise linguística sem veredito automatizado;
- falha explícita quando módulos essenciais não carregam;
- pré-visualização do texto extraído;
- pré-visualização dos fragmentos enviados à busca externa;
- informação de cobertura da análise;
- relatórios PDF gerados em memória;
- biblioteca temporária claramente identificada;
- tratamento de erros de arquivo e da SerpAPI;
- estrutura modular mínima.

## Executar localmente

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

## Configurar a SerpAPI

Crie `.streamlit/secrets.toml`:

```toml
SERPAPI_KEY = "sua_chave"
```

## Streamlit Community Cloud

1. Envie os arquivos para um repositório GitHub.
2. Crie um app apontando para `app.py`.
3. Em **Secrets**, adicione a chave `SERPAPI_KEY`.
4. Publique.

## Render

O projeto inclui `Dockerfile`. Crie um Web Service conectado ao GitHub e cadastre `SERPAPI_KEY` como variável de ambiente.

## Limitação importante

Esta versão não possui autenticação nem persistência. A biblioteca fica apenas na sessão do navegador. A busca web trabalha com snippets, não com o conteúdo integral das páginas.
