import React, { useState, useEffect, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Image, Platform, Animated, Easing } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { SERVER_URL, SOLVE_TIMEOUT_MS } from '../config';

const MESSAGES = [
  "Detecting star patterns...",
  "Computing celestial coordinates...",
  "Triangulating position...",
  "Calculating error radius..."
];

export default function LoadingScreen({ route, navigation }) {
  const { photoUri, location } = route.params;
  const [messageIdx, setMessageIdx] = useState(0);
  const spinValue = useRef(new Animated.Value(0)).current;
  const abortController = useRef(new AbortController());

  useEffect(() => {
    // Spin animation
    Animated.loop(
      Animated.timing(spinValue, {
        toValue: 1,
        duration: 4000,
        easing: Easing.linear,
        useNativeDriver: true
      })
    ).start();

    // Cycling messages
    const msgTimer = setInterval(() => {
      setMessageIdx(prev => (prev + 1) % MESSAGES.length);
    }, 2000);

    // Upload and process
    uploadImage();

    return () => {
      clearInterval(msgTimer);
      abortController.current.abort();
    };
  }, []);

  const spin = spinValue.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg']
  });

  const uploadImage = async () => {
    try {
      const formData = new FormData();
      
      const filename = photoUri.split('/').pop();
      const match = /\.(\w+)$/.exec(filename);
      const type = match ? `image/${match[1]}` : `image`;

      formData.append('image', {
        uri: photoUri,
        name: filename,
        type
      });

      // Format ISO without milliseconds for consistency
      const now = new Date();
      const isoString = now.toISOString().split('.')[0].replace('T', ' ');
      formData.append('timestamp', isoString);
      
      const tzOffset = -(now.getTimezoneOffset() / 60);
      formData.append('tz_offset_hours', tzOffset.toString());
      formData.append('camera_tilt_deg', '5.0');

      if (location) {
        formData.append('last_lat', location.latitude.toString());
        formData.append('last_lon', location.longitude.toString());
      }

      const timeoutId = setTimeout(() => {
        abortController.current.abort();
      }, SOLVE_TIMEOUT_MS);

      const response = await fetch(`${SERVER_URL}/estimate`, {
        method: 'POST',
        body: formData,
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        signal: abortController.current.signal
      });

      clearTimeout(timeoutId);

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error_message || "Server error");
      }
      
      navigation.replace('Result', { result: data, photoUri });

    } catch (error) {
      if (error.name === 'AbortError') {
        navigation.replace('Result', { 
          result: { success: false, error_message: "Timeout: Plate solving took too long." } 
        });
      } else {
        const errorMsg = error.message === "Network request failed" 
          ? "Cannot reach server. Ensure your PC is running start_api.ps1 and both devices are on the same WiFi network."
          : error.message;
        
        navigation.replace('Result', { 
          result: { success: false, error_message: errorMsg } 
        });
      }
    }
  };

  const handleCancel = () => {
    abortController.current.abort();
    navigation.goBack();
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.center}>
        <Animated.Text style={[styles.icon, { transform: [{ rotate: spin }] }]}>
          ✛
        </Animated.Text>
        
        <Text style={styles.messageText}>{MESSAGES[messageIdx]}</Text>
        
        <Image source={{ uri: photoUri }} style={styles.thumbnail} />
      </View>
      
      <View style={styles.bottomBar}>
        <TouchableOpacity style={styles.cancelButton} onPress={handleCancel}>
          <Text style={styles.cancelText}>Cancel</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0e1a',
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  icon: {
    fontSize: 80,
    color: '#4fc3f7',
    marginBottom: 40,
  },
  messageText: {
    color: '#ffffff',
    fontSize: 16,
    marginBottom: 40,
    fontFamily: Platform.OS === 'ios' ? 'Courier New' : 'monospace',
    textAlign: 'center',
    paddingHorizontal: 20,
  },
  thumbnail: {
    width: 120,
    height: 160,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: 'rgba(79, 195, 247, 0.3)',
  },
  bottomBar: {
    padding: 20,
    alignItems: 'center',
  },
  cancelButton: {
    paddingVertical: 12,
    paddingHorizontal: 30,
    borderRadius: 25,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
  },
  cancelText: {
    color: 'white',
    fontSize: 16,
  }
});
