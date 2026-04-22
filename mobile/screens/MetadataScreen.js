import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Platform,
  KeyboardAvoidingView,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

/**
 * MetadataScreen
 * Shown after every capture / gallery pick.
 * Mirrors the Streamlit UI: user confirms timestamp, timezone offset,
 * and camera tilt before triggering the solve.
 */
export default function MetadataScreen({ route, navigation }) {
  const { photoUri, exif, location } = route.params;

  // ── Derive a sensible default timestamp ────────────────────────────
  const deriveDefault = () => {
    // Try EXIF DateTimeOriginal: "2024:11:15 21:30:00"
    if (exif?.DateTimeOriginal) {
      try {
        const raw = exif.DateTimeOriginal.replace(':', '-').replace(':', '-');
        // raw might be "2024:11:15 21:30:00" → split on first space
        const parts = exif.DateTimeOriginal.split(' ');
        const datePart = parts[0].split(':').join('-');
        const timePart = parts[1] || '00:00:00';
        return `${datePart} ${timePart}`;
      } catch (_) {}
    }
    // Fall back to current local time
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    return (
      `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ` +
      `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
    );
  };

  const deriveDefaultTz = () => {
    // getTimezoneOffset returns minutes behind UTC (negative for east)
    return -(new Date().getTimezoneOffset() / 60);
  };

  const [timestamp, setTimestamp] = useState(deriveDefault());
  const [tzOffset, setTzOffset] = useState(String(deriveDefaultTz()));
  const [cameraTilt, setCameraTilt] = useState('5');
  const [exifDetected, setExifDetected] = useState(!!exif?.DateTimeOriginal);

  // ── Validation & navigation ─────────────────────────────────────────
  const handleEstimate = () => {
    // Validate timestamp format YYYY-MM-DD HH:MM:SS
    const tsRegex = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/;
    if (!tsRegex.test(timestamp.trim())) {
      Alert.alert(
        'Invalid Timestamp',
        'Please use the format: YYYY-MM-DD HH:MM:SS\nExample: 2024-11-15 21:30:00',
      );
      return;
    }

    const parsedTz = parseFloat(tzOffset);
    if (isNaN(parsedTz) || parsedTz < -14 || parsedTz > 14) {
      Alert.alert('Invalid Timezone', 'Timezone offset must be between -14 and +14 hours.');
      return;
    }

    const parsedTilt = parseFloat(cameraTilt);
    if (isNaN(parsedTilt) || parsedTilt < 0 || parsedTilt > 45) {
      Alert.alert('Invalid Tilt', 'Camera tilt must be between 0 and 45 degrees.');
      return;
    }

    navigation.replace('Loading', {
      photoUri,
      location,
      timestamp: timestamp.trim(),
      tz_offset_hours: parsedTz,
      camera_tilt_deg: parsedTilt,
    });
  };

  // ── Helpers for tz ± buttons ────────────────────────────────────────
  const stepTz = (delta) => {
    const current = parseFloat(tzOffset) || 0;
    const next = Math.max(-14, Math.min(14, Math.round((current + delta) * 2) / 2));
    setTzOffset(String(next));
  };

  const stepTilt = (delta) => {
    const current = parseInt(cameraTilt, 10) || 0;
    const next = Math.max(0, Math.min(45, current + delta));
    setCameraTilt(String(next));
  };

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          {/* Header */}
          <Text style={styles.header}>TARAPATH</Text>
          <Text style={styles.subheader}>Confirm Capture Metadata</Text>

          {/* EXIF detection notice */}
          {exifDetected ? (
            <View style={[styles.notice, styles.noticeSuccess]}>
              <Text style={styles.noticeText}>
                ✅ EXIF timestamp detected — override if needed.
              </Text>
            </View>
          ) : (
            <View style={[styles.notice, styles.noticeWarn]}>
              <Text style={styles.noticeText}>
                ⚠ No EXIF timestamp found — using current time. Please verify below.
              </Text>
            </View>
          )}

          {/* Accuracy tip */}
          <View style={styles.tipBox}>
            <Text style={styles.tipText}>
              💡 For best accuracy hold the camera pointing straight up at the zenith. Each
              degree of tilt ≈ 111 km of position error.
            </Text>
          </View>

          {/* Timestamp */}
          <Text style={styles.label}>CAPTURE TIMESTAMP (LOCAL TIME)</Text>
          <Text style={styles.sublabel}>Format: YYYY-MM-DD HH:MM:SS</Text>
          <TextInput
            style={styles.input}
            value={timestamp}
            onChangeText={setTimestamp}
            placeholder="2024-11-15 21:30:00"
            placeholderTextColor="rgba(255,255,255,0.3)"
            keyboardType="default"
            autoCorrect={false}
          />

          {/* Timezone */}
          <Text style={styles.label}>TIMEZONE OFFSET (HOURS FROM UTC)</Text>
          <Text style={styles.sublabel}>IST = +5.5  |  EST = -5.0  |  UTC = 0.0</Text>
          <View style={styles.stepRow}>
            <TouchableOpacity style={styles.stepBtn} onPress={() => stepTz(-0.5)}>
              <Text style={styles.stepBtnText}>−½</Text>
            </TouchableOpacity>
            <TextInput
              style={[styles.input, styles.inputCenter]}
              value={tzOffset}
              onChangeText={setTzOffset}
              keyboardType="numeric"
              placeholderTextColor="rgba(255,255,255,0.3)"
            />
            <TouchableOpacity style={styles.stepBtn} onPress={() => stepTz(0.5)}>
              <Text style={styles.stepBtnText}>+½</Text>
            </TouchableOpacity>
          </View>

          {/* Camera tilt */}
          <Text style={styles.label}>ESTIMATED CAMERA TILT (DEGREES)</Text>
          <Text style={styles.sublabel}>0 = perfectly level  |  45 = extreme tilt</Text>
          <View style={styles.stepRow}>
            <TouchableOpacity style={styles.stepBtn} onPress={() => stepTilt(-1)}>
              <Text style={styles.stepBtnText}>−1</Text>
            </TouchableOpacity>
            <TextInput
              style={[styles.input, styles.inputCenter]}
              value={cameraTilt}
              onChangeText={setCameraTilt}
              keyboardType="numeric"
              placeholderTextColor="rgba(255,255,255,0.3)"
            />
            <TouchableOpacity style={styles.stepBtn} onPress={() => stepTilt(1)}>
              <Text style={styles.stepBtnText}>+1</Text>
            </TouchableOpacity>
          </View>

          {/* Action buttons */}
          <TouchableOpacity style={styles.estimateBtn} onPress={handleEstimate}>
            <Text style={styles.estimateBtnText}>★  Calculate Position</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
            <Text style={styles.backBtnText}>← Back</Text>
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#0a0e1a' },
  scroll: { padding: 24, paddingBottom: 40 },

  header: {
    fontSize: 28,
    color: '#4fc3f7',
    fontFamily: Platform.OS === 'ios' ? 'Courier New' : 'monospace',
    fontWeight: 'bold',
    letterSpacing: 2,
    textAlign: 'center',
    marginTop: 10,
    marginBottom: 4,
  },
  subheader: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.6)',
    textAlign: 'center',
    marginBottom: 20,
  },

  notice: {
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    borderLeftWidth: 4,
  },
  noticeSuccess: { backgroundColor: 'rgba(76,175,80,0.15)', borderLeftColor: '#4caf50' },
  noticeWarn:   { backgroundColor: 'rgba(255,193,7,0.15)',  borderLeftColor: '#ffc107' },
  noticeText:   { color: '#ffffff', fontSize: 13 },

  tipBox: {
    backgroundColor: 'rgba(79,195,247,0.08)',
    borderRadius: 8,
    padding: 12,
    marginBottom: 24,
    borderWidth: 1,
    borderColor: 'rgba(79,195,247,0.2)',
  },
  tipText: { color: 'rgba(255,255,255,0.7)', fontSize: 13, lineHeight: 20 },

  label: {
    color: '#4fc3f7',
    fontSize: 11,
    fontFamily: Platform.OS === 'ios' ? 'Courier New' : 'monospace',
    letterSpacing: 1,
    marginBottom: 4,
    marginTop: 16,
  },
  sublabel: {
    color: 'rgba(255,255,255,0.4)',
    fontSize: 11,
    marginBottom: 6,
  },

  input: {
    flex: 1,
    backgroundColor: 'rgba(255,255,255,0.07)',
    borderWidth: 1,
    borderColor: 'rgba(79,195,247,0.3)',
    borderRadius: 8,
    color: '#ffffff',
    fontFamily: Platform.OS === 'ios' ? 'Courier New' : 'monospace',
    fontSize: 15,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  inputCenter: { textAlign: 'center', flex: 1 },

  stepRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  stepBtn: {
    backgroundColor: 'rgba(79,195,247,0.15)',
    borderWidth: 1,
    borderColor: 'rgba(79,195,247,0.4)',
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  stepBtnText: {
    color: '#4fc3f7',
    fontSize: 14,
    fontWeight: 'bold',
    fontFamily: Platform.OS === 'ios' ? 'Courier New' : 'monospace',
  },

  estimateBtn: {
    backgroundColor: '#4fc3f7',
    borderRadius: 10,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: 32,
  },
  estimateBtnText: {
    color: '#0a0e1a',
    fontSize: 16,
    fontWeight: 'bold',
    fontFamily: Platform.OS === 'ios' ? 'Courier New' : 'monospace',
    letterSpacing: 1,
  },

  backBtn: {
    alignItems: 'center',
    paddingVertical: 16,
  },
  backBtnText: { color: 'rgba(255,255,255,0.5)', fontSize: 14 },
});
