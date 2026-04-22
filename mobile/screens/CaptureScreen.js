import React, { useState, useEffect, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Platform, Alert } from 'react-native';
import { Camera, CameraView } from 'expo-camera';
import * as Location from 'expo-location';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function CaptureScreen({ navigation }) {
  const [hasPermission, setHasPermission] = useState(null);
  const [location, setLocation] = useState(null);
  const [countdown, setCountdown] = useState(0);
  const cameraRef = useRef(null);

  useEffect(() => {
    (async () => {
      const { status: cameraStatus } = await Camera.requestCameraPermissionsAsync();
      const { status: locationStatus } = await Location.requestForegroundPermissionsAsync();
      
      setHasPermission(cameraStatus === 'granted');
      
      if (locationStatus === 'granted') {
        try {
          const loc = await Location.getLastKnownPositionAsync();
          if (loc) {
            setLocation(loc.coords);
          } else {
            const currentLoc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Low });
            setLocation(currentLoc.coords);
          }
        } catch (e) {
          console.log('Location error:', e);
        }
      }
    })();
  }, []);

  const handleCapture = () => {
    if (countdown > 0) return;
    
    setCountdown(3);
    let counter = 3;
    
    const timer = setInterval(async () => {
      counter -= 1;
      setCountdown(counter);
      
      if (counter === 0) {
        clearInterval(timer);
        if (cameraRef.current) {
          try {
            const photo = await cameraRef.current.takePictureAsync({ quality: 1, exif: true });
            navigation.replace('Metadata', { 
              photoUri: photo.uri,
              exif: photo.exif,
              location: location
            });
          } catch (e) {
            Alert.alert("Camera Error", "Failed to take picture");
          }
        }
      }
    }, 1000);
  };

  if (hasPermission === null) {
    return <View style={styles.container}><Text style={styles.text}>Requesting permissions...</Text></View>;
  }
  if (hasPermission === false) {
    return <View style={styles.container}><Text style={styles.text}>No access to camera</Text></View>;
  }

  return (
    <SafeAreaView style={styles.container}>
      <CameraView style={styles.camera} ref={cameraRef}>
        <View style={styles.overlay}>
          {/* Crosshair */}
          <View style={styles.crosshairH} />
          <View style={styles.crosshairV} />
          <View style={styles.crosshairCircle} />
          
          {countdown > 0 && (
            <Text style={styles.countdownText}>{countdown}</Text>
          )}
        </View>
      </CameraView>
      
      <View style={styles.bottomBar}>
        <View style={styles.locationContainer}>
          <Text style={styles.monoText}>
            {location 
              ? `GPS: ${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)}` 
              : "GPS unavailable"}
          </Text>
        </View>
        
        <View style={styles.controls}>
          <TouchableOpacity 
            style={styles.cancelButton}
            onPress={() => navigation.goBack()}
          >
            <Text style={styles.cancelText}>Cancel</Text>
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={styles.captureBtn}
            onPress={handleCapture}
            disabled={countdown > 0}
          >
            <View style={styles.captureBtnInner} />
          </TouchableOpacity>
          
          <View style={{width: 60}} /> {/* Spacer for balance */}
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0e1a',
  },
  text: {
    color: 'white',
    textAlign: 'center',
    marginTop: 20,
  },
  camera: {
    flex: 1,
  },
  overlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'transparent',
  },
  crosshairH: {
    position: 'absolute',
    width: 40,
    height: 2,
    backgroundColor: 'rgba(79, 195, 247, 0.5)',
  },
  crosshairV: {
    position: 'absolute',
    width: 2,
    height: 40,
    backgroundColor: 'rgba(79, 195, 247, 0.5)',
  },
  crosshairCircle: {
    position: 'absolute',
    width: 100,
    height: 100,
    borderRadius: 50,
    borderWidth: 1,
    borderColor: 'rgba(79, 195, 247, 0.3)',
  },
  countdownText: {
    fontSize: 100,
    color: '#4fc3f7',
    fontWeight: 'bold',
    textShadowColor: 'rgba(0, 0, 0, 0.75)',
    textShadowOffset: {width: -1, height: 1},
    textShadowRadius: 10
  },
  bottomBar: {
    backgroundColor: '#0a0e1a',
    padding: 20,
    paddingBottom: Platform.OS === 'ios' ? 0 : 20,
  },
  locationContainer: {
    marginBottom: 20,
    alignItems: 'center',
  },
  monoText: {
    color: '#4fc3f7',
    fontFamily: Platform.OS === 'ios' ? 'Courier New' : 'monospace',
    fontSize: 12,
  },
  controls: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cancelButton: {
    padding: 10,
  },
  cancelText: {
    color: 'white',
    fontSize: 16,
  },
  captureBtn: {
    width: 70,
    height: 70,
    borderRadius: 35,
    backgroundColor: 'transparent',
    borderWidth: 3,
    borderColor: '#4fc3f7',
    alignItems: 'center',
    justifyContent: 'center',
  },
  captureBtnInner: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: '#4fc3f7',
  }
});
