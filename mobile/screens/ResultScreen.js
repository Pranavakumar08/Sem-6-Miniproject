import React, { useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Platform, Share } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { WebView } from 'react-native-webview';

export default function ResultScreen({ route, navigation }) {
  const { result } = route.params;

  useEffect(() => {
    if (result.success) {
      AsyncStorage.setItem('tarapath_last_result', JSON.stringify(result))
        .catch(e => console.log('Error saving result', e));
    }
  }, [result]);

  if (!result.success) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.errorCenter}>
          <Text style={styles.errorIcon}>⚠</Text>
          <Text style={styles.errorTitle}>Estimation Failed</Text>
          <Text style={styles.errorMessage}>{result.error_message}</Text>
        </View>
        <TouchableOpacity 
          style={styles.primaryButton}
          onPress={() => navigation.navigate('Capture')}
        >
          <Text style={styles.primaryButtonText}>Try Again</Text>
        </TouchableOpacity>
        <TouchableOpacity 
          style={styles.secondaryButton}
          onPress={() => navigation.navigate('Home')}
        >
          <Text style={styles.secondaryButtonText}>Back to Home</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  const { latitude, longitude, confidence, error_radius_km, stars_used } = result;
  
  const getConfidenceColor = (conf) => {
    if (conf >= 0.7) return '#4caf50'; // Green
    if (conf >= 0.4) return '#ffeb3b'; // Yellow
    return '#f44336'; // Red
  };

  const handleCopy = () => {
    const text = `LAT: ${latitude.toFixed(4)}, LON: ${longitude.toFixed(4)}`;
    Share.share({ message: text });
  };

  const handleShare = () => {
    Share.share({
      message: `My celestial position is ${latitude.toFixed(4)}°, ${longitude.toFixed(4)}° (Confidence: ${(confidence*100).toFixed(0)}%, Error: ${error_radius_km.toFixed(1)}km). Captured via Tarapath.`
    });
  };

  const mapHtml = `
    <!DOCTYPE html>
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
          body { margin: 0; padding: 0; background-color: #0a0e1a; }
          iframe { width: 100vw; height: 100vh; border: none; }
        </style>
      </head>
      <body>
        <iframe src="https://www.openstreetmap.org/export/embed.html?bbox=${longitude-0.1},${latitude-0.1},${longitude+0.1},${latitude+0.1}&layer=mapnik&marker=${latitude},${longitude}"></iframe>
      </body>
    </html>
  `;

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.resultHeader}>
        <Text style={styles.monoTitle}>LAT: {latitude.toFixed(4)}°</Text>
        <Text style={styles.monoTitle}>LON: {longitude.toFixed(4)}°</Text>
        
        <View style={styles.metricsRow}>
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>CONFIDENCE</Text>
            <Text style={[styles.metricValue, { color: getConfidenceColor(confidence) }]}>
              {(confidence * 100).toFixed(1)}%
            </Text>
          </View>
          <View style={styles.metric}>
            <Text style={styles.metricLabel}>ERROR RADIUS</Text>
            <Text style={styles.metricValue}>{error_radius_km.toFixed(1)} km</Text>
          </View>
        </View>
        
        {stars_used && stars_used.length > 0 && (
          <View style={styles.starsContainer}>
            <Text style={styles.metricLabel}>STARS USED:</Text>
            <Text style={styles.starsText}>{stars_used.join(', ')}</Text>
          </View>
        )}
      </View>

      <View style={styles.mapContainer}>
        <WebView 
          source={{ html: mapHtml }} 
          style={styles.map}
          scrollEnabled={false}
        />
      </View>

      <View style={styles.actionRow}>
        <TouchableOpacity style={styles.actionButton} onPress={handleCopy}>
          <Text style={styles.actionButtonText}>Copy Data</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.actionButton, styles.primaryAction]} onPress={() => navigation.navigate('Capture')}>
          <Text style={styles.primaryActionText}>Try Again</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.actionButton} onPress={handleShare}>
          <Text style={styles.actionButtonText}>Share</Text>
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
  errorCenter: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  errorIcon: {
    fontSize: 60,
    color: '#f44336',
    marginBottom: 20,
  },
  errorTitle: {
    fontSize: 24,
    color: 'white',
    marginBottom: 10,
    fontFamily: Platform.OS === 'ios' ? 'Courier New' : 'monospace',
  },
  errorMessage: {
    fontSize: 16,
    color: 'rgba(255,255,255,0.7)',
    textAlign: 'center',
    marginBottom: 40,
  },
  primaryButton: {
    backgroundColor: '#4fc3f7',
    padding: 15,
    borderRadius: 8,
    alignItems: 'center',
    marginHorizontal: 20,
    marginBottom: 15,
  },
  primaryButtonText: {
    color: '#0a0e1a',
    fontWeight: 'bold',
    fontSize: 16,
  },
  secondaryButton: {
    padding: 15,
    borderRadius: 8,
    alignItems: 'center',
    marginHorizontal: 20,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#4fc3f7',
  },
  secondaryButtonText: {
    color: '#4fc3f7',
    fontSize: 16,
  },
  resultHeader: {
    padding: 20,
    backgroundColor: 'rgba(255,255,255,0.05)',
  },
  monoTitle: {
    fontSize: 32,
    color: '#ffffff',
    fontFamily: Platform.OS === 'ios' ? 'Courier New' : 'monospace',
    fontWeight: 'bold',
    marginBottom: 5,
  },
  metricsRow: {
    flexDirection: 'row',
    marginTop: 20,
    justifyContent: 'space-between',
  },
  metric: {
    flex: 1,
  },
  metricLabel: {
    color: 'rgba(255,255,255,0.5)',
    fontSize: 12,
    marginBottom: 5,
    fontFamily: Platform.OS === 'ios' ? 'Courier New' : 'monospace',
  },
  metricValue: {
    color: '#ffffff',
    fontSize: 20,
    fontFamily: Platform.OS === 'ios' ? 'Courier New' : 'monospace',
  },
  starsContainer: {
    marginTop: 20,
    paddingTop: 15,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.1)',
  },
  starsText: {
    color: '#4fc3f7',
    fontFamily: Platform.OS === 'ios' ? 'Courier New' : 'monospace',
    fontSize: 14,
    marginTop: 5,
  },
  mapContainer: {
    flex: 1,
    margin: 20,
    borderRadius: 10,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(79,195,247,0.3)',
  },
  map: {
    flex: 1,
    backgroundColor: '#0a0e1a',
  },
  actionRow: {
    flexDirection: 'row',
    padding: 20,
    paddingBottom: Platform.OS === 'ios' ? 0 : 20,
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  actionButton: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
  },
  actionButtonText: {
    color: '#4fc3f7',
    fontSize: 14,
  },
  primaryAction: {
    backgroundColor: '#4fc3f7',
    borderRadius: 25,
    marginHorizontal: 10,
  },
  primaryActionText: {
    color: '#0a0e1a',
    fontWeight: 'bold',
    fontSize: 16,
  }
});
