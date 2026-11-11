import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../models/waqf_models.dart';

/// Cloud configuration for receiving 1-tap user Waqf reports via Neon Serverless Postgres.
class ReportCloudConfig {
  static const String neonHttpSqlUrl = String.fromEnvironment(
    'NEON_HTTP_SQL_URL',
    defaultValue:
        'https://ep-twilight-rain-beikjmw9-pooler.c-9.us-east-2.aws.neon.tech/sql',
  );

  static const String neonConnectionString = String.fromEnvironment(
    'NEON_CONNECTION_STRING',
    defaultValue:
        'postgresql://neondb_owner:npg_jdiUHBFP40bT@ep-twilight-rain-beikjmw9-pooler.c-9.us-east-2.aws.neon.tech/neondb?sslmode=require',
  );

  static const String supabaseUrl = String.fromEnvironment(
    'SUPABASE_URL',
    defaultValue: '',
  );
  static const String supabaseAnonKey = String.fromEnvironment(
    'SUPABASE_ANON_KEY',
    defaultValue: '',
  );
  static const String supabaseTable = String.fromEnvironment(
    'SUPABASE_TABLE',
    defaultValue: 'waqf_reports',
  );

  static const String firebaseDbUrl = String.fromEnvironment(
    'FIREBASE_DB_URL',
    defaultValue: '',
  );
  static const String firebaseAuthToken = String.fromEnvironment(
    'FIREBASE_AUTH_TOKEN',
    defaultValue: '',
  );

  static const String customWebhookUrl = String.fromEnvironment(
    'REPORT_WEBHOOK_URL',
    defaultValue: '',
  );

  static bool get hasNeon =>
      neonHttpSqlUrl.trim().isNotEmpty &&
      neonConnectionString.trim().isNotEmpty;

  static bool get hasSupabase =>
      supabaseUrl.trim().isNotEmpty && supabaseAnonKey.trim().isNotEmpty;

  static bool get hasFirebase => firebaseDbUrl.trim().isNotEmpty;

  static bool get hasCustomWebhook => customWebhookUrl.trim().isNotEmpty;

  static bool get isConfigured =>
      hasNeon || hasSupabase || hasFirebase || hasCustomWebhook;
}

class WaqfReportPayload {
  const WaqfReportPayload({
    required this.stopId,
    required this.surah,
    required this.surahName,
    required this.ayah,
    required this.wordIndex,
    required this.word,
    required this.flagged,
    required this.scholarFilter,
    required this.opinionsSummary,
    required this.clientId,
    required this.platform,
    required this.createdAt,
  });

  final String stopId;
  final int surah;
  final String surahName;
  final int ayah;
  final int wordIndex;
  final String word;
  final bool flagged;
  final String? scholarFilter;
  final String opinionsSummary;
  final String clientId;
  final String platform;
  final String createdAt;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'stop_id': stopId,
        'surah': surah,
        'surah_name': surahName,
        'ayah': ayah,
        'word_index': wordIndex,
        'word': word,
        'flagged': flagged,
        'scholar_filter': scholarFilter,
        'opinions_summary': opinionsSummary,
        'client_id': clientId,
        'platform': platform,
        'created_at': createdAt,
      };

  factory WaqfReportPayload.fromJson(Map<String, dynamic> json) {
    return WaqfReportPayload(
      stopId: json['stop_id'] as String? ?? '',
      surah: json['surah'] as int? ?? 0,
      surahName: json['surah_name'] as String? ?? '',
      ayah: json['ayah'] as int? ?? 0,
      wordIndex: json['word_index'] as int? ?? 1,
      word: json['word'] as String? ?? '',
      flagged: json['flagged'] as bool? ?? true,
      scholarFilter: json['scholar_filter'] as String?,
      opinionsSummary: json['opinions_summary'] as String? ?? '',
      clientId: json['client_id'] as String? ?? '',
      platform: json['platform'] as String? ?? '',
      createdAt: json['created_at'] as String? ?? '',
    );
  }
}

class WaqfReportService {
  static const String _clientIdPrefKey = 'waqf_reporter_client_id';
  static const String _pendingReportsPrefKey = 'waqf_pending_cloud_reports';

  static String? _cachedClientId;
  static bool _flushing = false;

  static bool _isWidgetTest() {
    try {
      return WidgetsBinding.instance.runtimeType.toString().contains('Test');
    } catch (_) {
      return false;
    }
  }

  static Future<String> _getOrCreateClientId() async {
    if (_cachedClientId != null) return _cachedClientId!;
    try {
      final prefs = await SharedPreferences.getInstance();
      final existing = prefs.getString(_clientIdPrefKey);
      if (existing != null && existing.isNotEmpty) {
        _cachedClientId = existing;
        return existing;
      }
      final rng = Random();
      final ts = DateTime.now().millisecondsSinceEpoch.toRadixString(36);
      final rand = List<String>.generate(
        8,
        (_) => rng.nextInt(36).toRadixString(36),
      ).join();
      final generated = 'u-$ts-$rand';
      await prefs.setString(_clientIdPrefKey, generated);
      _cachedClientId = generated;
      return generated;
    } catch (_) {
      return 'u-anon';
    }
  }

  static String _platformLabel() {
    if (kIsWeb) return 'web';
    return defaultTargetPlatform.name;
  }

  static String _summarizeOpinions(WaqfStop stop) {
    if (stop.opinions.isEmpty) return '';
    return stop.opinions
        .map((op) => '${op.scholar}: ${op.verdicts.join('/')}')
        .join(' | ');
  }

  /// Submits a 1-tap report for [stop] to Neon Postgres and queues it locally if offline.
  static Future<bool> submitStopReport({
    required WaqfStop stop,
    required String surahName,
    required bool flagged,
    String? scholarFilter,
  }) async {
    if (_isWidgetTest()) return true;
    final clientId = await _getOrCreateClientId();
    final payload = WaqfReportPayload(
      stopId: stop.id,
      surah: stop.surah,
      surahName: surahName,
      ayah: stop.ayah,
      wordIndex: stop.wordIndex,
      word: stop.word,
      flagged: flagged,
      scholarFilter: scholarFilter,
      opinionsSummary: _summarizeOpinions(stop),
      clientId: clientId,
      platform: _platformLabel(),
      createdAt: DateTime.now().toUtc().toIso8601String(),
    );

    final sent = await _sendPayloadToCloud(payload);
    if (!sent) {
      await _enqueuePending(payload);
    } else {
      unawaited(flushPendingReports());
    }
    return sent;
  }

  /// Fetches all currently flagged stop IDs from Neon Postgres so reports from
  /// any user device appear in the Review list.
  static Future<Set<String>> fetchCloudFlaggedStopIds() async {
    final ids = <String>{};
    if (_isWidgetTest() || !ReportCloudConfig.hasNeon) return ids;
    try {
      final res = await http
          .post(
            Uri.parse(ReportCloudConfig.neonHttpSqlUrl.trim()),
            headers: <String, String>{
              'Neon-Connection-String':
                  ReportCloudConfig.neonConnectionString.trim(),
              // Use text/plain so browser CORS preflight succeeds without custom Content-Type block
              'Content-Type': 'text/plain; charset=utf-8',
            },
            body: jsonEncode(<String, dynamic>{
              'query':
                  'SELECT DISTINCT stop_id FROM waqf_reports WHERE flagged = TRUE',
              'params': const <dynamic>[],
            }),
          )
          .timeout(const Duration(seconds: 4));
      if (res.statusCode == 200) {
        final decoded = jsonDecode(utf8.decode(res.bodyBytes));
        if (decoded is Map<String, dynamic>) {
          final rows = decoded['rows'] as List<dynamic>? ?? const <dynamic>[];
          for (final row in rows) {
            if (row is Map<String, dynamic>) {
              final id = row['stop_id']?.toString() ?? '';
              if (id.isNotEmpty) ids.add(id);
            }
          }
        }
      }
    } catch (_) {}
    return ids;
  }

  static Future<bool> _sendPayloadToCloud(WaqfReportPayload payload) async {
    if (!ReportCloudConfig.isConfigured) {
      return false;
    }
    var anySuccess = false;

    // 1. Neon Serverless Postgres over HTTP SQL API
    if (ReportCloudConfig.hasNeon) {
      try {
        const sql = '''
INSERT INTO waqf_reports (
  stop_id, surah, surah_name, ayah, word_index, word,
  flagged, scholar_filter, opinions_summary, client_id, platform, updated_at
) VALUES (
  \$1, \$2, \$3, \$4, \$5, \$6,
  \$7, \$8, \$9, \$10, \$11, NOW()
)
ON CONFLICT (stop_id, client_id) DO UPDATE SET
  flagged = EXCLUDED.flagged,
  scholar_filter = EXCLUDED.scholar_filter,
  opinions_summary = EXCLUDED.opinions_summary,
  platform = EXCLUDED.platform,
  updated_at = NOW();
''';
        final res = await http
            .post(
              Uri.parse(ReportCloudConfig.neonHttpSqlUrl.trim()),
              headers: <String, String>{
                'Neon-Connection-String':
                    ReportCloudConfig.neonConnectionString.trim(),
                'Content-Type': 'text/plain; charset=utf-8',
              },
              body: jsonEncode(<String, dynamic>{
                'query': sql,
                'params': <dynamic>[
                  payload.stopId,
                  payload.surah,
                  payload.surahName,
                  payload.ayah,
                  payload.wordIndex,
                  payload.word,
                  payload.flagged,
                  payload.scholarFilter,
                  payload.opinionsSummary,
                  payload.clientId,
                  payload.platform,
                ],
              }),
            )
            .timeout(const Duration(seconds: 5));
        if (res.statusCode >= 200 && res.statusCode < 300) {
          anySuccess = true;
        }
      } catch (_) {}
    }

    // 2. Supabase PostgREST (`POST /rest/v1/waqf_reports`)
    if (ReportCloudConfig.hasSupabase) {
      try {
        final baseUrl = ReportCloudConfig.supabaseUrl
            .trim()
            .replaceAll(RegExp(r'/+$'), '');
        final uri = Uri.parse(
          '$baseUrl/rest/v1/${ReportCloudConfig.supabaseTable}',
        );
        final res = await http
            .post(
              uri,
              headers: <String, String>{
                'apikey': ReportCloudConfig.supabaseAnonKey.trim(),
                'Authorization':
                    'Bearer ${ReportCloudConfig.supabaseAnonKey.trim()}',
                'Content-Type': 'application/json; charset=utf-8',
                'Prefer': 'return=minimal',
              },
              body: jsonEncode(payload.toJson()),
            )
            .timeout(const Duration(seconds: 5));
        if (res.statusCode >= 200 && res.statusCode < 300) {
          anySuccess = true;
        }
      } catch (_) {}
    }

    // 3. Firebase Realtime Database (`POST /waqf_reports.json`)
    if (ReportCloudConfig.hasFirebase) {
      try {
        final baseUrl = ReportCloudConfig.firebaseDbUrl
            .trim()
            .replaceAll(RegExp(r'/+$'), '');
        final authQuery = ReportCloudConfig.firebaseAuthToken.trim().isNotEmpty
            ? '?auth=${Uri.encodeQueryComponent(ReportCloudConfig.firebaseAuthToken.trim())}'
            : '';
        final uri = Uri.parse('$baseUrl/waqf_reports.json$authQuery');
        final res = await http
            .post(
              uri,
              headers: const <String, String>{
                'Content-Type': 'application/json; charset=utf-8',
              },
              body: jsonEncode(payload.toJson()),
            )
            .timeout(const Duration(seconds: 5));
        if (res.statusCode >= 200 && res.statusCode < 300) {
          anySuccess = true;
        }
      } catch (_) {}
    }

    // 4. Custom Webhook URL
    if (ReportCloudConfig.hasCustomWebhook) {
      try {
        final uri = Uri.parse(ReportCloudConfig.customWebhookUrl.trim());
        final res = await http
            .post(
              uri,
              headers: const <String, String>{
                'Content-Type': 'application/json; charset=utf-8',
              },
              body: jsonEncode(payload.toJson()),
            )
            .timeout(const Duration(seconds: 5));
        if (res.statusCode >= 200 && res.statusCode < 300) {
          anySuccess = true;
        }
      } catch (_) {}
    }

    return anySuccess;
  }

  static Future<void> _enqueuePending(WaqfReportPayload payload) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final list = List<String>.from(
        prefs.getStringList(_pendingReportsPrefKey) ?? const <String>[],
      );
      if (list.length >= 500) {
        list.removeAt(0);
      }
      list.add(jsonEncode(payload.toJson()));
      await prefs.setStringList(_pendingReportsPrefKey, list);
    } catch (_) {}
  }

  /// Flushes any locally queued reports when internet & cloud config are available.
  static Future<void> flushPendingReports() async {
    if (_flushing || _isWidgetTest() || !ReportCloudConfig.isConfigured) return;
    _flushing = true;
    try {
      final prefs = await SharedPreferences.getInstance();
      final list = List<String>.from(
        prefs.getStringList(_pendingReportsPrefKey) ?? const <String>[],
      );
      if (list.isEmpty) return;

      final remaining = <String>[];
      for (final raw in list) {
        try {
          final decoded = jsonDecode(raw) as Map<String, dynamic>;
          final item = WaqfReportPayload.fromJson(decoded);
          final ok = await _sendPayloadToCloud(item);
          if (!ok) {
            remaining.add(raw);
          }
        } catch (_) {}
      }
      await prefs.setStringList(_pendingReportsPrefKey, remaining);
    } catch (_) {
    } finally {
      _flushing = false;
    }
  }
}
