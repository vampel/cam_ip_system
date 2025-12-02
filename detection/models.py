# detection/models.py
from django.db import models
from django.utils import timezone

class Camera(models.Model):
    name = models.CharField(max_length=100)
    stream_url = models.URLField()
    location = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class DetectionRecord(models.Model):
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE)
    person_count = models.IntegerField()
    chair_count = models.IntegerField()
    occupancy_rate = models.FloatField()  # Porcentaje
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        indexes = [
            models.Index(fields=['camera', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]

class DailyReport(models.Model):
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE)
    date = models.DateField()
    avg_occupancy = models.FloatField()
    peak_occupancy = models.IntegerField()
    total_detections = models.IntegerField()