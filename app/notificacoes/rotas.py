from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models import Usuario
from app.notificacoes.schemas import InscricaoNotificacaoCreate, InscricaoNotificacaoResponse, LogEventoResponse
from app.notificacoes.servico import ServicoNotificacoes

router = APIRouter(prefix="/notificacoes", tags=["Notificações"])

@router.post("/inscrever", response_model=InscricaoNotificacaoResponse, status_code=status.HTTP_201_CREATED)
def inscrever_notificacao(
    dados: InscricaoNotificacaoCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user)
):
    servico = ServicoNotificacoes(db)
    try:
        return servico.inscrever_usuario(usuario_id=usuario_atual.id, ocorrencia_id=dados.ocorrencia_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/ocorrencia/{ocorrencia_id}/logs", response_model=list[LogEventoResponse])
def listar_logs_evento(ocorrencia_id: int, db: Session = Depends(get_db)):
    servico = ServicoNotificacoes(db)
    return servico.listar_logs_ocorrencia(ocorrencia_id)