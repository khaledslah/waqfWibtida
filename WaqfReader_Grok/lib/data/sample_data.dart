import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../models/waqf_models.dart';

const catalogAssetPath = 'assets/app_feed/catalog.json';
const _reviewStateServerUrl = 'http://127.0.0.1:8765/api/review-state';

class SurahCatalogEntry {
  const SurahCatalogEntry({
    required this.number,
    required this.name,
    required this.ayahCount,
    required this.stopCount,
    required this.uthmaniStopCount,
    required this.asset,
    this.sourceTag,
  });

  final int number;
  final String name;
  final int ayahCount;
  final int stopCount;
  final int uthmaniStopCount;
  final String asset;
  final String? sourceTag;

  factory SurahCatalogEntry.fromJson(Map<String, dynamic> json) {
    return SurahCatalogEntry(
      number: json['number'] as int,
      name: json['name'] as String,
      ayahCount: json['ayahCount'] as int? ?? 0,
      stopCount: json['stopCount'] as int? ?? 0,
      uthmaniStopCount: json['uthmaniStopCount'] as int? ?? 0,
      asset: json['asset'] as String,
      sourceTag: json['sourceTag'] as String?,
    );
  }

  SurahIndexEntry toIndexEntry({required bool loaded}) {
    return SurahIndexEntry(
      number: number,
      name: name,
      status: loaded
          ? SurahLoadStatus.inProgress
          : SurahLoadStatus.notStarted,
      detail:
          'الآيات ${arabicDigits(ayahCount)} · ${arabicDigits(stopCount)} وقف · ${arabicDigits(uthmaniStopCount)} عثماني',
    );
  }
}

class AppFeedBundle {
  const AppFeedBundle({
    required this.stops,
    required this.ayahs,
    required this.source,
    required this.surah,
    required this.surahName,
  });

  final List<WaqfStop> stops;
  final List<Ayah> ayahs;
  final String source;
  final int surah;
  final String surahName;

  static List<String> _parseStringList(dynamic raw, String fallback) {
    if (raw is List) {
      final list = raw.map((e) => e?.toString() ?? '').where((s) => s.isNotEmpty).toList();
      if (list.isNotEmpty) return list;
    } else if (raw is String && raw.trim().isNotEmpty) {
      return [raw.trim()];
    }
    return [fallback];
  }

  static List<bool> _parseBoolList(dynamic raw, int targetLength) {
    final out = <bool>[];
    if (raw is List) {
      for (final item in raw) {
        out.add(item == true);
      }
    } else if (raw is bool) {
      out.add(raw);
    }
    while (out.length < targetLength) {
      out.add(false);
    }
    return out;
  }

  static AppFeedBundle fromJson(Map<String, dynamic> json) {
    final stopsJson = json['stops'] as List<dynamic>? ?? const [];
    final ayahsJson = json['ayahs'] as List<dynamic>? ?? const [];

    final stops = <WaqfStop>[
      for (final raw in stopsJson)
        WaqfStop(
          id: raw['id'] as String,
          surah: raw['surah'] as int,
          ayah: raw['ayah'] as int,
          wordIndex: raw['wordIndex'] as int? ?? 1,
          word: raw['word'] as String,
          fallbackSymbol: raw['symbol'] != null
              ? stopSymbolFromFeed(raw['symbol'] as String?)
              : null,
          fallbackLabel: raw['label'] as String?,
          fallbackReason: raw['reason'] as String?,
          inUthmaniMushaf: raw['inUthmaniMushaf'] as bool? ?? false,
          isVerseEnd: raw['isVerseEnd'] as bool? ?? false,
          textPage: raw['textPage'] as int?,
          aiSuggestion: raw['aiSuggestion'] as String?,
          opinions: [
            for (final op in (raw['opinions'] as List<dynamic>? ?? const []))
              () {
                final verdicts = _parseStringList(op['verdict'], 'جائز');
                final rawLabels = _parseStringList(op['verdictLabel'], 'ج');
                final rawSyms = _parseStringList(op['symbol'], 'jaiz');
                final symbols = <StopSymbol>[
                  for (var i = 0; i < verdicts.length; i++)
                    stopSymbolFromFeed(
                      i < rawSyms.length ? rawSyms[i] : rawSyms.first,
                    ),
                ];
                final labels = <String>[
                  for (var i = 0; i < verdicts.length; i++)
                    i < rawLabels.length
                        ? rawLabels[i]
                        : defaultVerdictLabelForSymbol(symbols[i]),
                ];
                final qilaFlags = _parseBoolList(op['isQila'], verdicts.length);
                return ScholarOpinion(
                  scholar: op['scholar'] as String? ?? 'مجهول',
                  targetWord:
                      op['targetWord'] as String? ?? (raw['word'] as String? ?? ''),
                  verdicts: verdicts,
                  verdictLabels: labels,
                  symbols: symbols,
                  isQila: qilaFlags,
                  book: op['book'] as String? ?? 'علل الوقوف',
                  page: op['page']?.toString(),
                  comment: op['comment'] as String?,
                  fromMargin: false,
                );
              }(),
          ],
        ),
    ];

    final ayahs = <Ayah>[
      for (final raw in ayahsJson)
        Ayah(
          number: raw['number'] as int,
          words: [
            for (final w in (raw['words'] as List<dynamic>? ?? const []))
              AyahWord(
                w['text'] as String,
                w['stopId'] as String?,
              ),
          ],
        ),
    ];

    final tag = json['sourceTag'] as String? ?? 'apparatus';
    final batches = (json['sourceBatch'] as List<dynamic>? ?? const []).length;

    return AppFeedBundle(
      stops: stops,
      ayahs: ayahs,
      source: '$tag · $batches batches',
      surah: json['surah'] as int? ?? 0,
      surahName: json['surahName'] as String? ?? '',
    );
  }

  static Future<AppFeedBundle> loadAsset(String assetPath) async {
    final text = await rootBundle.loadString('assets/$assetPath');
    final decoded = jsonDecode(text);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Invalid app feed shape');
    }
    return AppFeedBundle.fromJson(decoded);
  }
}

enum ReaderLoadState { loading, ready, error }

class ReaderController extends ChangeNotifier {
  int tab = 0;
  double quranSize = 26;
  String? selectedStopId;
  final Set<String> sentToReview = <String>{};
  final Set<String> favorites = <String>{};
  final Set<String> verified = <String>{};

  bool hideVerseEnd = true;
  bool hideUthmani = true;
  String? selectedScholar;
  ReviewListFilter reviewFilter = ReviewListFilter.all;

  static const List<String?> scholarOptions = <String?>[
    null,
    'السجاوندي',
    'الأشموني',
    'الداني',
    'ابن الأنباري',
    'النحاس',
  ];

  ReaderLoadState loadState = ReaderLoadState.loading;
  String? loadError;
  String sourceLabel = '';

  List<SurahCatalogEntry> catalog = const [];
  int currentSurah = 0;
  String currentSurahName = '';

  List<WaqfStop> sampleStops = const [];
  List<Ayah> yusufAyahs = const [];

  /// Kept name for mushaf screen compatibility — current surah ayahs.
  List<Ayah> get currentAyahs => yusufAyahs;

  List<SurahIndexEntry> get sampleSurahs => [
        for (final s in catalog)
          s.toIndexEntry(loaded: s.number == currentSurah),
      ];

  Future<void> bootstrap({int initialSurah = 1}) async {
    loadState = ReaderLoadState.loading;
    loadError = null;
    notifyListeners();
    try {
      await _restorePrefs();
      await _loadCatalog();
      await loadSurah(initialSurah, notify: false);
    } catch (e) {
      loadError = 'تعذّر تحميل فهرس المصحف أو بيانات السورة.';
      loadState = ReaderLoadState.error;
    }
    notifyListeners();
  }

  Future<void> _restorePrefs() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      sentToReview
        ..clear()
        ..addAll(prefs.getStringList('sentToReview') ?? const []);
      favorites
        ..clear()
        ..addAll(prefs.getStringList('favorites') ?? const []);
      verified
        ..clear()
        ..addAll(prefs.getStringList('verified') ?? const []);
    } catch (_) {
      // Prefs optional on some platforms.
    }
    unawaited(_pullAndPushServerReviewState());
  }

  Future<void> _persistPrefs() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setStringList('sentToReview', sentToReview.toList());
      await prefs.setStringList('favorites', favorites.toList());
      await prefs.setStringList('verified', verified.toList());
    } catch (_) {}
    unawaited(_syncReviewStateToServer());
  }

  Map<String, dynamic> _buildFlaggedStopDetails() {
    final activeIds = <String>{
      ...sentToReview,
      ...favorites,
      ...verified,
    };
    final details = <String, dynamic>{};
    for (final stop in sampleStops) {
      if (activeIds.contains(stop.id)) {
        details[stop.id] = {
          'id': stop.id,
          'surah': stop.surah,
          'surahName': currentSurahName,
          'ayah': stop.ayah,
          'wordIndex': stop.wordIndex,
          'word': stop.word,
          'flagged': sentToReview.contains(stop.id),
          'favorite': favorites.contains(stop.id),
          'verified': verified.contains(stop.id),
        };
      }
    }
    return details;
  }

  Future<void> _pullAndPushServerReviewState() async {
    try {
      final res = await http
          .get(Uri.parse(_reviewStateServerUrl))
          .timeout(const Duration(milliseconds: 1200));
      if (res.statusCode == 200) {
        final decoded = jsonDecode(utf8.decode(res.bodyBytes));
        if (decoded is Map<String, dynamic>) {
          var changed = false;
          for (final id in (decoded['sentToReview'] as List<dynamic>? ?? const [])) {
            if (id is String && sentToReview.add(id)) changed = true;
          }
          for (final id in (decoded['favorites'] as List<dynamic>? ?? const [])) {
            if (id is String && favorites.add(id)) changed = true;
          }
          for (final id in (decoded['verified'] as List<dynamic>? ?? const [])) {
            if (id is String && verified.add(id)) changed = true;
          }
          if (changed) {
            notifyListeners();
          }
        }
      }
    } catch (_) {}
    await _syncReviewStateToServer();
  }

  Future<void> _syncReviewStateToServer() async {
    try {
      await http
          .post(
            Uri.parse(_reviewStateServerUrl),
            headers: const {'Content-Type': 'application/json; charset=utf-8'},
            body: jsonEncode({
              'sentToReview': sentToReview.toList(),
              'favorites': favorites.toList(),
              'verified': verified.toList(),
              'flaggedDetails': _buildFlaggedStopDetails(),
            }),
          )
          .timeout(const Duration(milliseconds: 1200));
    } catch (_) {}
  }

  Future<void> _loadCatalog() async {
    final text = await rootBundle.loadString(catalogAssetPath);
    final decoded = jsonDecode(text);
    if (decoded is! Map<String, dynamic>) {
      throw const FormatException('Invalid catalog');
    }
    final list = decoded['surahs'] as List<dynamic>? ?? const [];
    catalog = [
      for (final raw in list)
        SurahCatalogEntry.fromJson(raw as Map<String, dynamic>),
    ];
  }

  Future<void> loadSurah(int number, {bool notify = true}) async {
    SurahCatalogEntry? entry;
    for (final s in catalog) {
      if (s.number == number) {
        entry = s;
        break;
      }
    }
    if (entry == null) {
      throw StateError('Surah $number not in catalog');
    }
    if (notify) {
      loadState = ReaderLoadState.loading;
      notifyListeners();
    }
    try {
      final bundle = await AppFeedBundle.loadAsset(entry.asset);
      sampleStops = bundle.stops;
      yusufAyahs = bundle.ayahs;
      sourceLabel = bundle.source;
      currentSurah = bundle.surah;
      currentSurahName = bundle.surahName;
      selectedStopId = _defaultSelectedId(sampleStops);
      loadState = ReaderLoadState.ready;
      loadError = null;
      if (sentToReview.isNotEmpty || favorites.isNotEmpty || verified.isNotEmpty) {
        unawaited(_syncReviewStateToServer());
      }
    } catch (e) {
      loadError = 'تعذّر تحميل ${entry.name}.';
      loadState = ReaderLoadState.error;
    }
    if (notify) notifyListeners();
  }

  static String? _defaultSelectedId(List<WaqfStop> stops) {
    final visible = stops.where((s) => !s.isVerseEnd && !s.inUthmaniMushaf);
    if (visible.isNotEmpty) return visible.first.id;
    return stops.isNotEmpty ? stops.first.id : null;
  }

  WaqfStop? stopById(String id) {
    for (final stop in sampleStops) {
      if (stop.id == id) return stop;
    }
    return null;
  }

  bool isVerseEnd(WaqfStop stop) => stop.isVerseEnd;

  bool isStopVisible(WaqfStop stop) {
    if (selectedScholar != null && !stop.hasScholar(selectedScholar!)) {
      return false;
    }
    if (hideVerseEnd && isVerseEnd(stop)) return false;
    if (hideUthmani && stop.inUthmaniMushaf) return false;
    return true;
  }

  int get visibleStopCount => sampleStops.where(isStopVisible).length;

  void setSelectedScholar(String? scholar) {
    if (selectedScholar == scholar) return;
    selectedScholar = scholar;
    notifyListeners();
  }

  void toggleHideVerseEnd() {
    hideVerseEnd = !hideVerseEnd;
    notifyListeners();
  }

  void toggleHideUthmani() {
    hideUthmani = !hideUthmani;
    notifyListeners();
  }

  void showAllStops() {
    if (!hideVerseEnd && !hideUthmani) return;
    hideVerseEnd = false;
    hideUthmani = false;
    notifyListeners();
  }

  void select(String id) {
    if (selectedStopId == id) return;
    selectedStopId = id;
    notifyListeners();
  }

  Future<void> markForReview(String id) async {
    if (sentToReview.add(id)) {
      notifyListeners();
      await _persistPrefs();
    }
  }

  Future<void> toggleSent(String id) async {
    if (!sentToReview.add(id)) {
      sentToReview.remove(id);
    }
    notifyListeners();
    await _persistPrefs();
  }

  bool isSent(String id) => sentToReview.contains(id);

  bool isFavorite(String id) => favorites.contains(id);

  Future<void> toggleFavorite(String id) async {
    if (!favorites.add(id)) favorites.remove(id);
    notifyListeners();
    await _persistPrefs();
  }

  bool isVerified(String id) => verified.contains(id);

  Future<void> toggleVerified(String id) async {
    if (!verified.add(id)) verified.remove(id);
    notifyListeners();
    await _persistPrefs();
  }

  void setReviewFilter(ReviewListFilter filter) {
    if (reviewFilter == filter) return;
    reviewFilter = filter;
    notifyListeners();
  }

  void setTab(int value) {
    if (tab == value) return;
    tab = value;
    notifyListeners();
  }

  void setQuranSize(double value) {
    if (quranSize == value) return;
    quranSize = value;
    notifyListeners();
  }

  List<WaqfStop> get reviewItems {
    final filter = reviewFilter;
    if (filter == ReviewListFilter.all) return List<WaqfStop>.from(sampleStops);
    return sampleStops.where((s) {
      switch (filter) {
        case ReviewListFilter.all:
          return true;
        case ReviewListFilter.needsAttention:
          return s.needsReview || sentToReview.contains(s.id);
        case ReviewListFilter.favorites:
          return favorites.contains(s.id);
        case ReviewListFilter.verified:
          return verified.contains(s.id);
        case ReviewListFilter.unsettled:
          return s.symbol == StopSymbol.unsettled || s.hasNullVerdict;
        case ReviewListFilter.ai:
          return s.hasAiSuggestion;
        case ReviewListFilter.uthmani:
          return s.inUthmaniMushaf;
        case ReviewListFilter.verseEnd:
          return s.isVerseEnd;
      }
    }).toList();
  }
}

