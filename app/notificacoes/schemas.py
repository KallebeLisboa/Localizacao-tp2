from datetime import datetime
from pydantic import BaseModel

class InscricaoNotificacaoCreate(BaseModel):
    ocorrencia_id: int

class InscricaoNotificacaoResponse(BaseModel):
    id: int
    usuario_id: int
    ocorrencia_id: int
    criado_em: datetime

    class Config:
        from_attributes = True

class LogEventoResponse(BaseModel):
    id: int
    ocorrencia_id: int
    status_anterior: str | None
    status_novo: str
    mensagem: str
    criado_em: datetime

    class Config:
        from_attributes = True