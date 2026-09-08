# Carrer
Carrer transforma evidencias reais do trabalho de profissionais de software em contribuicoes, competencias, impactos e artefatos profissionais rastreaveis.
Curriculo, LinkedIn, STAR stories e matriz de habilidades sao saidas derivadas. O nucleo do produto e a camada de conhecimento baseada em evidencia.
## Problema que o Carrer resolve
Engenheiros acumulam anos de evidencias (work items, commits, revisoes, documentacao), mas normalmente reconstr?em sua trajetoria por memoria quando precisam comunicar impacto profissional.
Carrer organiza essas evidencias para responder com rastreabilidade:
- o que foi feito
- qual foi a participacao
- quais resultados e impactos podem ser afirmados
- quais evidencias suportam cada afirmacao
## Estado atual de maturidade
- MVP funcional e executavel localmente
- arquitetura em modularizacao incremental
- nao e SaaS
- nao possui interface web
- nao deve ser apresentado como produto pronto para producao
## Fluxo conceitual atual
```text
External Source
-> Collector
-> Normalization Layer
-> Evidence Graph (immutable)
-> Inference Engine
-> Observation
-> Knowledge Graph (versioned, regenerable)
-> Analysis Agents
-> Artifact Generators
```
## Instalacao
Requisitos:
- Python 3.11+
- pip
```bash
python -m pip install -e ".[dev]"
```
## Testes
```bash
python -m pytest tests/ -v
python -m pytest tests/ --cov=src --cov-report=term-missing
```
A suite deve permanecer integralmente verde. Execute a suite para obter a contagem atual de testes.
## Lint
```bash
python -m ruff check src/ scripts/ tests/
```
## Formatacao
```bash
python -m ruff format --check src/ scripts/ tests/
```
## Mypy
Escopo tipado obrigatorio atual:
```bash
python -m mypy src/carrer/
```
## CI
O workflow `.github/workflows/ci.yml` executa em pushes e pull requests para `main` e `develop`,
com Python 3.11 e 3.12 no Ubuntu 24.04. Cada versao executa Ruff check, Ruff format --check,
mypy e pytest com coverage (terminal e XML, sem threshold minimo). Uma falha nao cancela a outra versao.
Os comandos partem da raiz do repositorio, com UTC e UTF-8. Cada job cria um venv novo e instala
as versoes de `.github/requirements-ci.txt`, incluindo dependencias transitivas e setuptools;
o extra `dev` continua definido em `pyproject.toml`. Para reproduzir a instalacao em um venv local:
```bash
python -m pip install -r .github/requirements-ci.txt
python -m pip install --no-build-isolation -c .github/requirements-ci.txt -e ".[dev]"
python -m pip check
```
Atualize os pins de dependencias em conjunto e valide os quality gates nas duas versoes Python.
O cache armazena apenas downloads do pip, considera ambos os arquivos de dependencias e e opcional.
As versoes patch do Python e a imagem do runner podem receber atualizacoes; os logs registram o runtime usado.
O CI usa somente `contents: read`, actions fixadas por SHA e checkout sem persistir credenciais.
A auditoria registra actor, triggering_actor, evento, ref, ref_name, SHA, repositorio, Python e runner,
sem imprimir secrets, tokens ou o ambiente completo. Antes de instalar dependencias, o job exige
`HEAD == github.sha` e working tree limpo. Em pull requests, esse SHA corresponde ao merge commit
de teste do GitHub. O Dependabot verifica atualizacoes de actions semanalmente.
## Execucao local do MVP
```bash
python scripts/run_mvp.py
```
Ou com um export `source_export_v1`:
```bash
python scripts/run_mvp.py examples/azure_devops_export_sample.json
```
## CLI
Consultas e revisoes explicitas sobre um graph store existente:
```bash
carrer --store graph.json contributions discover
carrer --store graph.json contributions promote --candidate-id <candidate-id> --actor <actor> --decided-at <ISO8601>
carrer --store graph.json contributions reject --candidate-id <candidate-id> --actor <actor> --decided-at <ISO8601> --reason "..."
carrer --store graph.json analyses generate --contribution-id <contribution-id>
carrer --store graph.json analyses accept --contribution-id <contribution-id> --actor <actor> --decided-at <ISO8601>
carrer --store graph.json analyses reject --contribution-id <contribution-id> --actor <actor> --decided-at <ISO8601> --reason "..."
carrer --store graph.json claims generate --analysis-id <contribution-analysis-id>
carrer --store graph.json claims accept --analysis-id <contribution-analysis-id> --candidate-id <candidate-id> --actor <actor> --decided-at <ISO8601>
carrer --store graph.json claims reject --analysis-id <contribution-analysis-id> --candidate-id <candidate-id> --actor <actor> --decided-at <ISO8601> --reason "..."
carrer --store graph.json artifacts build --claim-id <career-claim-id> --artifact-type resume_claims --audience public --created-at <ISO8601>
carrer --store graph.json artifacts accept --claim-id <career-claim-id> --artifact-type resume_claims --audience public --created-at <ISO8601> --actor <actor> --decided-at <ISO8601>
carrer --store graph.json artifacts reject --claim-id <career-claim-id> --artifact-type resume_claims --audience public --created-at <ISO8601> --actor <actor> --decided-at <ISO8601> --reason "..."
carrer --store graph.json exports build --artifact-id <professional-artifact-id> --export-scope external --export-format markdown --created-at <ISO8601>
carrer --store graph.json exports accept --artifact-id <professional-artifact-id> --export-scope external --export-format markdown --created-at <ISO8601> --output-directory <path> --actor <actor> --decided-at <ISO8601>
carrer --store graph.json exports reject --artifact-id <professional-artifact-id> --export-scope external --export-format markdown --created-at <ISO8601> --actor <actor> --decided-at <ISO8601> --reason "..."
carrer --store graph.json exports list
carrer --store graph.json exports integrity --receipt-id <artifact-export-receipt-id> --output-directory <path> --checked-at <ISO8601>
carrer --store graph.json exports repair build --receipt-id <artifact-export-receipt-id> --output-directory <path> --checked-at <ISO8601> --created-at <ISO8601>
carrer --store graph.json exports repair accept --receipt-id <artifact-export-receipt-id> --output-directory <path> --checked-at <ISO8601> --created-at <ISO8601> --actor <actor> --decided-at <ISO8601> --verified-at <ISO8601>
carrer --store graph.json exports repair reject --receipt-id <artifact-export-receipt-id> --output-directory <path> --checked-at <ISO8601> --created-at <ISO8601> --actor <actor> --decided-at <ISO8601> --reason "..."
```
`exports integrity` e read-only: exige um receipt persistido conhecido, `--output-directory` e `--checked-at` explicitos, verifica receipt, filesystem local, provenance e audit pelo contrato do dominio e retorna o `ArtifactExportIntegrityReport` sem salvar o graph, criar/remover/alterar arquivos, corrigir nada ou executar repair. Ele nao faz scan global do diretorio: um arquivo final publicado antes de uma falha ao salvar o graph, sem `ArtifactExportReceipt` duravel, nao pode ser selecionado. `integrity graph` continua sendo a verificacao separada do estado persistido do graph.
`exports repair build` e read-only: regenera o report de integridade atual a partir do receipt e do diretorio explicitos e gera somente a proposta `ArtifactExportRepairCandidate` em memoria. `exports repair accept` regenera esse mesmo estado atual, recebe uma decisao humana explicita e pode reparar edges no graph e remover apenas o arquivo temporario residual; `--verified-at` e o timestamp explicito da verificacao final. `exports repair reject` tambem regenera o estado atual, registra a decisao humana e e somente audit. Nenhum deles aceita report/candidate JSON, arquivo ou stdin arbitrario. Nao existe transacao ACID ou rollback automatico entre filesystem e graph: a remocao do arquivo temporario pode ocorrer antes de `store.save()`, portanto uma falha ao salvar pode deixar o filesystem consistente enquanto o JSON duravel ainda nao contem receipt/audit de repair.
`analyses generate`, `claims generate`, `artifacts build` e `exports build` sao read-only: carregam o store, regeneram o contrato deterministico atual em memoria e nao salvam, criam nodes, criam edges, registram audit ou escrevem arquivos. `artifacts build` exige selecao explicita por um ou mais `--claim-id`; `exports build` exige um `ProfessionalArtifact` aceito, `source_type=career_claim`, escopo, formato e `created-at` explicitos. Nenhuma claim ou artifact e escolhido automaticamente, nao ha payload JSON arbitrario, arquivo, stdin ou selecao por ranking. `analyses accept/reject`, `claims accept/reject`, `artifacts accept/reject` e `exports accept/reject` sao decisoes humanas explicitas: a CLI regenera a analise, candidate, artifact draft ou export candidate atual no mesmo processo, recebe somente identidade e parametros deterministico-reprodutiveis, delega a revisao para a application layer, valida a pos-condicao em memoria e so entao salva o JSON graph. `exports accept` tambem exige `--output-directory` explicito. Privacy/audience continuam governadas pelo dominio; export externo exige `artifact_safe`, export interno aceita `internal` ou `artifact_safe`, e erros de incompatibilidade sao propagados sem fallback. O export local cruza duas fronteiras: o dominio escreve o arquivo Markdown final antes da CLI salvar o graph JSON com `ArtifactExportReceipt`; se esse save falhar, o arquivo final pode existir sem receipt duravel no JSON antigo. Integridade e repair de export permanecem operacoes separadas.
## Configuracao de conectores
Conectores atualmente suportados por scripts locais:
- Azure DevOps
- GitLab
Fluxo tipico:
```bash
python scripts/mcp_collect.py collect-azure
python scripts/collect_gitlab_user.py
python scripts/career_pipeline.py
```
Importacao de descricoes de vaga locais (`.txt` / `.md`):
```bash
python scripts/import_job_descriptions.py path/to/job-descriptions data/job_descriptions_source_export.json
python scripts/career_pipeline.py --job-descriptions path/to/job-descriptions
```
## Privacidade
Niveis de privacidade:
- `private`: nunca exportado
- `internal`: uso local
- `artifact_safe`: seguro para artefatos profissionais
- `exported`: aprovado para sistemas externos
Regras centrais:
- evidencias sao imutaveis
- conhecimento e revisavel
- saidas publicaveis devem respeitar os limites de privacidade
## Estrutura resumida do repositorio
```text
carrer/
??? AGENTS.md
??? CLAUDE.md
??? README.md
??? pyproject.toml
??? docs/
?   ??? product/
?   ??? architecture/
?   ??? development/
?   ??? specs/
??? scripts/
??? src/
?   ??? career_intelligence_mvp.py
?   ??? carrer/
?       ??? domain/
?       ??? artifacts/
?       ??? inference/
?       ??? ingestion/
?       ??? storage/
??? tests/
```
## Links importantes
- Visao: `docs/product/vision.md`
- Principios: `docs/product/principles.md`
- Glossario: `docs/product/glossary.md`
- Arquitetura: `docs/architecture/current-state.md`, `docs/architecture/target-state.md`
- Politica do repositorio: `docs/development/repository-policy.md`
