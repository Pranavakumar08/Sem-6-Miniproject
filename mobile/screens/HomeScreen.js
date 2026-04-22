import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform, LayoutAnimation } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useIsFocused } from '@react-navigation/native';

import * as ImagePicker from 'expo-image-picker';
import * as Location from 'expo-location';

export default function HomeScreen({ navigation }) {
  const [lastResult, setLastResult] = useState(null);
  const [howToExpanded, setHowToExpanded] = useState(false);
  const isFocused = useIsFocused();

  useEffect(() => {
    if (isFocused) {
      loadLastResult();
    }
  }, [isFocused]);

  const loadLastResult = async () => {
    try {
      const stored = await AsyncStorage.getItem('tarapath_last_result');
      if (stored) {
        setLastResult(JSON.parse(stored));
      }
    } catch (e) {
      console.log('Failed to load last result', e);
    }
  };

  const toggleHowTo = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setHowToExpanded(!howToExpanded);
  };

  const handleUpload = async () => {
    const { status: mediaStatus } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (mediaStatus !== 'granted') {
      alert('Sorry, we need camera roll permissions to make this work!');
      return;
    }

    let result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      exif: true,
      quality: 1,
    });

    if (!result.canceled && result.assets && result.assets.length > 0) {
      const asset = result.assets[0];
      // Grab location if possible to pass along
      let location = null;
      const { status: locationStatus } = await Location.requestForegroundPermissionsAsync();
      if (locationStatus === 'granted') {
        try {
          location = await Location.getLastKnownPositionAsync();
        } catch(e) {}
      }
      navigation.navigate('Metadata', {
        photoUri: asset.uri,
        exif: asset.exif,
        location: location ? location.coords : null
      });
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>TARAPATH</Text>
        <Text style={styles.subtitle}>Celestial Navigation System</Text>
      </View>

      <View style={styles.center}>
        <View style={styles.actionsRow}>
          <TouchableOpacity 
            style={styles.captureButton}
            onPress={() => navigation.navigate('Capture')}
          >
            <Text style={styles.captureIcon}>★</Text>
            <Text style={styles.buttonLabel}>Capture</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={styles.captureButton}
            onPress={handleUpload}
          >
            <Text style={styles.captureIcon}>🖼</Text>
            <Text style={styles.buttonLabel}>Upload</Text>
          </TouchableOpacity>
        </View>
      </View>

      {lastResult && (
        <View style={styles.lastResultCard}>
          <Text style={styles.lastResultTitle}>Last Known Position</Text>
          <Text style={styles.monoText}>LAT: {lastResult.latitude.toFixed(4)}°</Text>
          <Text style={styles.monoText}>LON: {lastResult.longitude.toFixed(4)}°</Text>
          <Text style={styles.monoText}>Confidence: {(lastResult.confidence * 100).toFixed(1)}%</Text>
          <Text style={styles.monoText}>Error: {lastResult.error_radius_km.toFixed(1)} km</Text>
        </View>
      )}

      <TouchableOpacity style={styles.howToHeader} onPress={toggleHowTo}>
        <Text style={styles.howToTitle}>How to use {howToExpanded ? '▼' : '▶'}</Text>
      </TouchableOpacity>
      
      {howToExpanded && (
        <View style={styles.howToBody}>
          <Text style={styles.howToText}>• Point camera straight up at night sky</Text>
          <Text style={styles.howToText}>• Ensure stars are visible</Text>
          <Text style={styles.howToText}>• Keep phone level for best accuracy</Text>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0e1a',
    padding: 20,
  },
  header: {
    alignItems: 'center',
    marginTop: 40,
    marginBottom: 60,
  },
  title: {
    fontSize: 42,
    color: '#4fc3f7',
    fontFamily: Platform.OS === 'ios' ? 'Courier New' : 'monospace',
    fontWeight: 'bold',
    letterSpacing: 2,
  },
  subtitle: {
    fontSize: 16,
    color: '#ffffff',
    marginTop: 10,
    opacity: 0.8,
  },
  center: {
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 40,
  },
  actionsRow: {
    flexDirection: 'row',
    gap: 30,
  },
  captureButton: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: 'rgba(79, 195, 247, 0.2)',
    borderWidth: 2,
    borderColor: '#4fc3f7',
    alignItems: 'center',
    justifyContent: 'center',
  },
  captureIcon: {
    fontSize: 40,
    color: '#4fc3f7',
    marginBottom: 5,
  },
  buttonLabel: {
    color: '#4fc3f7',
    fontSize: 14,
    fontFamily: Platform.OS === 'ios' ? 'Courier New' : 'monospace',
    fontWeight: 'bold',
  },
  lastResultCard: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    padding: 20,
    borderRadius: 10,
    marginBottom: 40,
    borderLeftWidth: 4,
    borderLeftColor: '#4fc3f7',
  },
  lastResultTitle: {
    color: '#4fc3f7',
    fontSize: 14,
    marginBottom: 10,
    textTransform: 'uppercase',
  },
  monoText: {
    color: '#ffffff',
    fontFamily: Platform.OS === 'ios' ? 'Courier New' : 'monospace',
    fontSize: 14,
    marginBottom: 5,
  },
  howToHeader: {
    paddingVertical: 15,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.1)',
  },
  howToTitle: {
    color: '#4fc3f7',
    fontSize: 16,
    textTransform: 'uppercase',
  },
  howToBody: {
    paddingVertical: 15,
  },
  howToText: {
    color: '#ffffff',
    fontSize: 14,
    marginBottom: 8,
    opacity: 0.8,
  }
});
