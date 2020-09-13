from django.db import models
from uuid import uuid4


class BaseModel(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid4)

    class Meta:
        abstract = True


class Clubs(BaseModel):
    name = models.TextField()

    class Meta:
        db_table = 'clubs'


class Members(BaseModel):
    club = models.ForeignKey(Clubs, on_delete=models.CASCADE)
    dancer_uuid = models.UUIDField()

    class Meta:
        db_table = 'members'
