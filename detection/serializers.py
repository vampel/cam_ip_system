# detection/serializers.py
from rest_framework import serializers
from .models import Camera, DetectionRecord

class CameraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Camera
        fields = ['id', 'name', 'stream_url', 'location', 'is_active']

class DetectionRecordSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(source='camera.name', read_only=True)
    
    class Meta:
        model = DetectionRecord
        fields = ['id', 'camera_name', 'person_count', 'chair_count', 
                 'occupancy_rate', 'timestamp']