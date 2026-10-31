import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/waqf_models.dart';

const catalogAssetPath = 'assets/app_feed/catalog.json';

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

  static AppFeedBundle fromJson(Map<String, dynamic> json) {
    final stopsJson = json['stops'] as List<dynamic>? ?? const [];
    final ayahsJson = json['ayahs'] as List<dynamic>? ?? const [];

    final stops = <WaqfStop>[
      for (final raw in stopsJson)
        WaqfStop(
          id: raw['id'] as String,
          surah: raw['surah'] as int,
          ayah: raw['ayah'] as int,
          word: raw['word'] as String,
          symbol: stopSymbolFromFeed(raw['symbol'] as String?),
          label: raw['label'] as String? ?? 'غير محسوم',
          reason: raw['reason'] as String? ?? '',
          inUthmaniMushaf: raw['inUthmaniMushaf'] as bool? ?? false,
          isVerseEnd: raw['isVerseEnd'] as bool? ?? false,
          textPage: raw['textPage'] as int?,
          aiSuggestion: raw['aiSuggestion'] as String?,
          opinions: [
            for (final op in (raw['opinions'] as List<dynamic>? ?? const []))
              ScholarOpinion(
                scholar: op['scholar'] as String? ?? 'مجهول',
                verdict: op['verdict'] as String?,
                book: op['book'] as String? ?? 'علل الوقوف',
                page: op['page']?.toString(),
                comment: op['comment'] as String?,
                fromMargin: (op['scholar'] as String?) != 'السجاوندي',
              ),
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
  ReviewListFilter reviewFilter = ReviewListFilter.all;

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
      loadState = ReaderLoadState.ready;
    } catch (e) {
      loadError = 'تعذّر تحميل فهرس المصحف أو بيانات السورة.';
      loadState = ReaderLoadState.error;
    }
    notifyListeners();
  }

  Future<void> _restorePrefs() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      favorites
        ..clear()
        ..addAll(prefs.getStringList('favorites') ?? const []);
      verified
        ..clear()
        ..addAll(prefs.getStringList('verified') ?? const []);
    } catch (_) {
      // Prefs optional on some platforms.
    }
  }

  Future<void> _persistPrefs() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setStringList('favorites', favorites.toList());
      await prefs.setStringList('verified', verified.toList());
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
      // Keep favorites/verified across surahs; clear ephemeral "sent" queue only.
      sentToReview.clear();
      loadState = ReaderLoadState.ready;
      loadError = null;
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
    if (hideVerseEnd && isVerseEnd(stop)) return false;
    if (hideUthmani && stop.inUthmaniMushaf) return false;
    return true;
  }

  int get visibleStopCount => sampleStops.where(isStopVisible).length;

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

  void markForReview(String id) {
    if (sentToReview.add(id)) notifyListeners();
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

