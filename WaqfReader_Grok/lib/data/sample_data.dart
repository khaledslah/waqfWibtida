import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../models/waqf_models.dart';
import '../utils/report_service.dart';

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
    required this.stopsById,
    required this.ayahs,
    required this.ayahChunks,
    required this.source,
    required this.surah,
    required this.surahName,
  });

  final List<WaqfStop> stops;
  final Map<String, WaqfStop> stopsById;
  final List<Ayah> ayahs;
  final List<List<Ayah>> ayahChunks;
  final String source;
  final int surah;
  final String surahName;

  static final Map<String, AppFeedBundle> _assetCache =
      <String, AppFeedBundle>{};
  static final Map<String, Future<AppFeedBundle>> _inflightLoads =
      <String, Future<AppFeedBundle>>{};

  static AppFeedBundle? getCached(String assetPath) => _assetCache[assetPath];

  static List<String> _parseStringList(dynamic raw, String fallback) {
    if (raw is List) {
      final list = raw
          .map((e) => e?.toString() ?? '')
          .where((s) => s.isNotEmpty)
          .toList();
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

  static List<int>? _parseWordSpan(dynamic raw) {
    if (raw is! List || raw.length < 2) return null;
    final start = raw[0] is int ? raw[0] as int : int.tryParse('${raw[0]}');
    final end = raw[1] is int ? raw[1] as int : int.tryParse('${raw[1]}');
    if (start == null || end == null) return null;
    return <int>[start, end];
  }

  static List<WaqfDemoAndMeaning> _parseDemosAndMeanings(dynamic raw) {
    if (raw is! List || raw.isEmpty) return const <WaqfDemoAndMeaning>[];
    final out = <WaqfDemoAndMeaning>[];
    for (final item in raw) {
      if (item is! Map) continue;
      final map = Map<String, dynamic>.from(item);
      final verdict = map['verdict']?.toString().trim() ?? '';
      if (verdict.isEmpty) continue;
      final attrRaw = map['attributedTo']?.toString().trim();
      out.add(
        WaqfDemoAndMeaning(
          verdict: verdict,
          isQila: map['isQila'] == true,
          attributedTo:
              (attrRaw != null && attrRaw.isNotEmpty) ? attrRaw : null,
          waqfSegmentWords: _parseWordSpan(map['waqfSegmentWords']),
          ibtidaSegmentWords: _parseWordSpan(map['ibtidaSegmentWords']),
          waqfDemo: map['waqfDemo']?.toString() ?? '',
          ibtidaDemo: map['ibtidaDemo']?.toString() ?? '',
          meaningAtWaqf: map['meaningAtWaqf']?.toString() ?? '',
          meaningAtIbtida: map['meaningAtIbtida']?.toString() ?? '',
          meaningIfConnected: map['meaningIfConnected']?.toString() ?? '',
        ),
      );
    }
    return out;
  }

  /// Groups ayahs into balanced chunks (~75 words per chunk) so ListView.builder
  /// only lays out visible screen chunks while keeping ayah boundaries intact.
  static List<List<Ayah>> _buildAyahChunks(
    List<Ayah> ayahs, {
    int targetWordsPerChunk = 75,
  }) {
    if (ayahs.isEmpty) return const <List<Ayah>>[];
    final chunks = <List<Ayah>>[];
    var currentChunk = <Ayah>[];
    var currentWords = 0;

    for (final ayah in ayahs) {
      currentChunk.add(ayah);
      currentWords += ayah.words.length + 1;
      if (currentWords >= targetWordsPerChunk) {
        chunks.add(currentChunk);
        currentChunk = <Ayah>[];
        currentWords = 0;
      }
    }
    if (currentChunk.isNotEmpty) {
      chunks.add(currentChunk);
    }
    return chunks;
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
                final qilaFlags =
                    _parseBoolList(op['isQila'], verdicts.length);
                return ScholarOpinion(
                  scholar: op['scholar'] as String? ?? 'مجهول',
                  targetWord: op['targetWord'] as String? ??
                      (raw['word'] as String? ?? ''),
                  verdicts: verdicts,
                  verdictLabels: labels,
                  symbols: symbols,
                  isQila: qilaFlags,
                  book: op['book'] as String? ?? 'علل الوقوف',
                  page: op['page']?.toString(),
                  comment: op['comment'] as String?,
                  fromMargin: false,
                  demosAndMeanings:
                      _parseDemosAndMeanings(op['demosAndMeanings']),
                );
              }(),
          ],
        ),
    ];

    final stopsById = <String, WaqfStop>{
      for (final stop in stops) stop.id: stop,
    };

    final ayahs = <Ayah>[
      for (final raw in ayahsJson)
        Ayah(
          number: raw['number'] as int,
          words: [
            for (var wi = 0;
                wi < (raw['words'] as List<dynamic>? ?? const []).length;
                wi++)
              () {
                final w = (raw['words'] as List<dynamic>)[wi]
                    as Map<String, dynamic>;
                final parsedIndex = w['index'] is int
                    ? w['index'] as int
                    : int.tryParse('${w['index'] ?? ''}');
                return AyahWord(
                  w['text'] as String,
                  w['stopId'] as String?,
                  parsedIndex ?? (wi + 1),
                );
              }(),
          ],
        ),
    ];

    final tag = json['sourceTag'] as String? ?? 'apparatus';
    final batches =
        (json['sourceBatch'] as List<dynamic>? ?? const []).length;

    return AppFeedBundle(
      stops: stops,
      stopsById: stopsById,
      ayahs: ayahs,
      ayahChunks: _buildAyahChunks(ayahs),
      source: '$tag · $batches batches',
      surah: json['surah'] as int? ?? 0,
      surahName: json['surahName'] as String? ?? '',
    );
  }

  static Future<AppFeedBundle> loadAsset(String assetPath) {
    final cached = _assetCache[assetPath];
    if (cached != null) {
      return SynchronousFuture<AppFeedBundle>(cached);
    }
    final inflight = _inflightLoads[assetPath];
    if (inflight != null) {
      return inflight;
    }
    final future = _loadAndParseAsset(assetPath);
    _inflightLoads[assetPath] = future;
    return future;
  }

  static Future<AppFeedBundle> _loadAndParseAsset(String assetPath) async {
    try {
      final text = await rootBundle.loadString('assets/$assetPath', cache: false);
      final decoded = jsonDecode(text);
      if (decoded is! Map<String, dynamic>) {
        throw const FormatException('Invalid app feed shape');
      }
      final bundle = AppFeedBundle.fromJson(decoded);
      _assetCache[assetPath] = bundle;
      return bundle;
    } finally {
      _inflightLoads.remove(assetPath);
    }
  }
}

enum ReaderLoadState { loading, ready, error }

class ReaderController extends ChangeNotifier {
  int tab = 0;
  double quranSize = 26;
  String? selectedStopId;

  /// When false, mushaf never paints demo waqf/ibtida spans.
  bool demoHighlightActive = false;

  /// Scholar whose demo spans are highlighted in the mushaf (nullable = auto).
  String? selectedDemoScholar;

  /// Which demosAndMeanings entry is active for highlighting (null = first).
  int? selectedDemoIndex;

  final Set<String> sentToReview = <String>{};
  final Set<String> favorites = <String>{};
  final Set<String> verified = <String>{};

  bool hideVerseEnd = true;
  bool hideUthmani = true;
  String? selectedScholar;
  ReviewListFilter reviewFilter = ReviewListFilter.all;

  /// Fixed bottom stop panel (معاني / أقوال).
  bool stopDockOpen = false;

  /// 0 = معاني (demo), 1 = أقوال.
  int stopDockTab = 0;

  /// Dock + bottom nav shared theme. Light by default; only flips via toggle.
  bool panelDark = false;

  /// Session-only: show center swipe coaching once per app start.
  bool swipeHintAvailable = true;

  /// Returns true if a swipe-hint overlay should play (once per app start).
  bool consumeSwipeHint() {
    if (!swipeHintAvailable) return false;
    swipeHintAvailable = false;
    return true;
  }

  void dismissSwipeHint() {
    swipeHintAvailable = false;
  }

  static const String scholarAllSentinel = '__all__';

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
  Map<String, WaqfStop> _stopsById = const <String, WaqfStop>{};
  List<Ayah> yusufAyahs = const [];
  List<List<Ayah>> _ayahChunks = const <List<Ayah>>[];
  int? _cachedVisibleStopCount;
  bool _disposed = false;
  bool _warmingUp = false;

  /// Kept name for mushaf screen compatibility — current surah ayahs.
  List<Ayah> get currentAyahs => yusufAyahs;

  /// Pre-chunked ayahs for instant virtualized rendering in MushafScreen.
  List<List<Ayah>> get currentAyahChunks => _ayahChunks;

  List<SurahIndexEntry> get sampleSurahs => [
        for (final s in catalog)
          s.toIndexEntry(loaded: s.number == currentSurah),
      ];

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }

  Future<void> bootstrap({int initialSurah = 1}) async {
    loadState = ReaderLoadState.loading;
    loadError = null;
    notifyListeners();
    try {
      await _restorePrefs();
      await _loadCatalog();
      await loadSurah(initialSurah, notify: false);
      unawaited(_warmUpCatalogAssets());
    } catch (e) {
      loadError = 'تعذّر تحميل فهرس المصحف أو بيانات السورة.';
      loadState = ReaderLoadState.error;
    }
    if (!_disposed) {
      notifyListeners();
    }
  }

  static bool _isRunningInWidgetTest() {
    try {
      final name = WidgetsBinding.instance.runtimeType.toString();
      return name.contains('Test');
    } catch (_) {
      return false;
    }
  }

  /// Preloads all 114 Surahs into memory in the background (largest Surahs first)
  /// so switching to any Surah is a 0ms in-memory pointer swap.
  Future<void> _warmUpCatalogAssets() async {
    if (_warmingUp || _disposed || _isRunningInWidgetTest()) return;
    _warmingUp = true;
    try {
      const priorityNumbers = <int>[
        2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 16, 17, 18, 19, 20, 26, 36, 55, 67,
      ];
      final ordered = <SurahCatalogEntry>[];
      final seen = <int>{};
      for (final num in priorityNumbers) {
        for (final s in catalog) {
          if (s.number == num && seen.add(s.number)) {
            ordered.add(s);
          }
        }
      }
      for (final s in catalog) {
        if (seen.add(s.number)) {
          ordered.add(s);
        }
      }
      for (final entry in ordered) {
        if (_disposed) return;
        if (AppFeedBundle.getCached(entry.asset) != null) continue;
        try {
          await AppFeedBundle.loadAsset(entry.asset);
        } catch (_) {}
        await Future<void>.delayed(const Duration(milliseconds: 2));
      }
    } finally {
      _warmingUp = false;
    }
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
    unawaited(WaqfReportService.flushPendingReports());
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
    for (final id in activeIds) {
      final stop = _stopsById[id];
      if (stop != null) {
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
      final cloudIds = await WaqfReportService.fetchCloudFlaggedStopIds();
      if (cloudIds.isNotEmpty) {
        var cloudChanged = false;
        for (final id in cloudIds) {
          if (sentToReview.add(id)) cloudChanged = true;
        }
        if (cloudChanged && !_disposed) {
          notifyListeners();
        }
      }
    } catch (_) {}
    try {
      final res = await http
          .get(Uri.parse(_reviewStateServerUrl))
          .timeout(const Duration(milliseconds: 1200));
      if (res.statusCode == 200) {
        final decoded = jsonDecode(utf8.decode(res.bodyBytes));
        if (decoded is Map<String, dynamic>) {
          var changed = false;
          for (final id
              in (decoded['sentToReview'] as List<dynamic>? ?? const [])) {
            if (id is String && sentToReview.add(id)) changed = true;
          }
          for (final id
              in (decoded['favorites'] as List<dynamic>? ?? const [])) {
            if (id is String && favorites.add(id)) changed = true;
          }
          for (final id
              in (decoded['verified'] as List<dynamic>? ?? const [])) {
            if (id is String && verified.add(id)) changed = true;
          }
          if (changed && !_disposed) {
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

  void _applyBundle(AppFeedBundle bundle) {
    sampleStops = bundle.stops;
    _stopsById = bundle.stopsById;
    yusufAyahs = bundle.ayahs;
    _ayahChunks = bundle.ayahChunks;
    _cachedVisibleStopCount = null;
    sourceLabel = bundle.source;
    currentSurah = bundle.surah;
    currentSurahName = bundle.surahName;
    selectedStopId = _defaultSelectedId(sampleStops);
    loadState = ReaderLoadState.ready;
    loadError = null;
    if (sentToReview.isNotEmpty ||
        favorites.isNotEmpty ||
        verified.isNotEmpty) {
      unawaited(_syncReviewStateToServer());
    }
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

    // Fast path: if already cached in memory, switch synchronously in 0ms!
    final cached = AppFeedBundle.getCached(entry.asset);
    if (cached != null) {
      _applyBundle(cached);
      if (notify && !_disposed) notifyListeners();
      return;
    }

    // Only show full-screen loading spinner if no Surah is currently displayed.
    if (notify && yusufAyahs.isEmpty) {
      loadState = ReaderLoadState.loading;
      if (!_disposed) notifyListeners();
    }
    try {
      final bundle = await AppFeedBundle.loadAsset(entry.asset);
      _applyBundle(bundle);
    } catch (e) {
      loadError = 'تعذّر تحميل ${entry.name}.';
      loadState = ReaderLoadState.error;
    }
    if (notify && !_disposed) notifyListeners();
  }

  static String? _defaultSelectedId(List<WaqfStop> stops) {
    for (final s in stops) {
      if (!s.isVerseEnd && !s.inUthmaniMushaf) return s.id;
    }
    return stops.isNotEmpty ? stops.first.id : null;
  }

  WaqfStop? stopById(String id) => _stopsById[id];

  bool isVerseEnd(WaqfStop stop) => stop.isVerseEnd;

  bool isStopVisible(WaqfStop stop) {
    if (selectedScholar != null && !stop.hasScholar(selectedScholar!)) {
      return false;
    }
    if (hideVerseEnd && isVerseEnd(stop)) return false;
    if (hideUthmani && stop.inUthmaniMushaf) return false;
    return true;
  }

  int get visibleStopCount {
    final cached = _cachedVisibleStopCount;
    if (cached != null) return cached;
    var count = 0;
    for (final s in sampleStops) {
      if (isStopVisible(s)) count++;
    }
    _cachedVisibleStopCount = count;
    return count;
  }

  void setSelectedScholar(String? scholar) {
    if (selectedScholar == scholar) return;
    selectedScholar = scholar;
    _cachedVisibleStopCount = null;
    notifyListeners();
  }

  /// Popup menus cannot use null values reliably — map sentinel ↔ null.
  void setSelectedScholarFromMenu(String value) {
    setSelectedScholar(value == scholarAllSentinel ? null : value);
  }

  /// Opens the dock. Default tab when opening from closed is الأقوال (1).
  /// If the dock is already open on another stop, keeps the current tab.
  void openStopDock(String stopId, {int? tab}) {
    final stop = stopById(stopId);
    if (stop == null) return;

    // Same stop while dock open → toggle closed.
    if (stopDockOpen && selectedStopId == stopId) {
      closeStopDock();
      return;
    }

    // Dock already open on a different stop → keep tab choice.
    if (stopDockOpen) {
      navigateStopDock(stopId);
      return;
    }

    // Fresh open: caller tab or default الأقوال.
    _showStopInDock(stop, tab: (tab ?? 1).clamp(0, 1));
  }

  /// Move dock to another stop without toggle-close behavior; keeps tab.
  void navigateStopDock(String stopId) {
    final stop = stopById(stopId);
    if (stop == null) return;
    _showStopInDock(stop, tab: stopDockTab);
  }

  void _showStopInDock(WaqfStop stop, {required int tab}) {
    selectedStopId = stop.id;
    stopDockOpen = true;
    var t = tab.clamp(0, 1);
    if (!stop.hasDemosAndMeanings) t = 1;
    stopDockTab = t;
    selectedDemoIndex = 0;
    _ensureDemoHighlightForDock(stop);
    notifyListeners();
  }

  List<WaqfStop> get visibleStops {
    return sampleStops.where(isStopVisible).toList(growable: false);
  }

  /// Next/prev visible waqf in the dock. [delta] > 0 = next. Returns false at ends.
  bool stepVisibleStop(int delta) {
    if (!stopDockOpen || delta == 0) return false;
    final stops = visibleStops;
    if (stops.isEmpty) return false;
    final id = selectedStopId;
    var idx = id == null ? -1 : stops.indexWhere((s) => s.id == id);
    if (idx < 0) idx = 0;
    final next = idx + (delta > 0 ? 1 : -1);
    if (next < 0 || next >= stops.length) return false;
    navigateStopDock(stops[next].id);
    return true;
  }

  void _ensureDemoHighlightForDock(WaqfStop stop) {
    if (!stop.hasDemosAndMeanings) {
      demoHighlightActive = false;
      selectedDemoScholar = null;
      selectedDemoIndex = null;
      return;
    }
    ScholarOpinion? op;
    if (selectedScholar != null && selectedScholar!.isNotEmpty) {
      final preferred = stop.opinionForScholar(selectedScholar);
      if (preferred != null && preferred.demosAndMeanings.isNotEmpty) {
        op = preferred;
      }
    }
    if (op == null) {
      for (final o in stop.opinions) {
        if (o.demosAndMeanings.isNotEmpty) {
          op = o;
          break;
        }
      }
    }
    demoHighlightActive = true;
    selectedDemoScholar = op?.scholar;
    selectedDemoIndex ??= 0;
  }

  void setStopDockTab(int tab) {
    final t = tab.clamp(0, 1);
    if (!stopDockOpen) return;
    if (stopDockTab == t) return;
    stopDockTab = t;
    // Keep mushaf highlight while the dock stays open.
    final id = selectedStopId;
    final stop = id == null ? null : stopById(id);
    if (stop != null) _ensureDemoHighlightForDock(stop);
    notifyListeners();
  }

  void togglePanelTheme() {
    panelDark = !panelDark;
    notifyListeners();
  }

  void closeStopDock() {
    if (!stopDockOpen &&
        !demoHighlightActive &&
        selectedDemoScholar == null &&
        selectedDemoIndex == null) {
      return;
    }
    stopDockOpen = false;
    demoHighlightActive = false;
    selectedDemoScholar = null;
    selectedDemoIndex = null;
    notifyListeners();
  }

  void toggleHideVerseEnd() {
    hideVerseEnd = !hideVerseEnd;
    _cachedVisibleStopCount = null;
    notifyListeners();
  }

  void toggleHideUthmani() {
    hideUthmani = !hideUthmani;
    _cachedVisibleStopCount = null;
    notifyListeners();
  }

  void showAllStops() {
    if (!hideVerseEnd && !hideUthmani) return;
    hideVerseEnd = false;
    hideUthmani = false;
    _cachedVisibleStopCount = null;
    notifyListeners();
  }

  void select(String id) {
    selectedStopId = id;
    // Modal sheet path: select stop, close dock, no demo spans.
    demoHighlightActive = false;
    selectedDemoScholar = null;
    selectedDemoIndex = null;
    stopDockOpen = false;
    notifyListeners();
  }

  void clearDemoHighlight() {
    if (!demoHighlightActive &&
        selectedDemoScholar == null &&
        selectedDemoIndex == null) {
      return;
    }
    demoHighlightActive = false;
    selectedDemoScholar = null;
    selectedDemoIndex = null;
    notifyListeners();
  }

  /// Enables mushaf demo spans (+ optional meanings sheet) for a stop.
  void activateDemoHighlight(
    String stopId, {
    String? scholar,
    int demoIndex = 0,
  }) {
    selectedStopId = stopId;
    demoHighlightActive = true;
    selectedDemoScholar = scholar;
    selectedDemoIndex = demoIndex;
    notifyListeners();
  }

  void selectDemo({
    required String scholar,
    required int demoIndex,
  }) {
    demoHighlightActive = true;
    selectedDemoScholar = scholar;
    selectedDemoIndex = demoIndex;
    notifyListeners();
  }

  /// Visible stops that have demos, in mushaf reading order (ayah, word).
  List<WaqfStop> get demoNavStops {
    final out = <WaqfStop>[];
    for (final s in sampleStops) {
      if (!isStopVisible(s) || !s.hasDemosAndMeanings) continue;
      out.add(s);
    }
    out.sort((a, b) {
      final byAyah = a.ayah.compareTo(b.ayah);
      if (byAyah != 0) return byAyah;
      return a.wordIndex.compareTo(b.wordIndex);
    });
    return out;
  }

  ScholarOpinion? _demoOpinionFor(WaqfStop stop) {
    final preferred = selectedDemoScholar ?? selectedScholar;
    if (preferred != null && preferred.isNotEmpty) {
      final op = stop.opinionForScholar(preferred);
      if (op != null && op.demosAndMeanings.isNotEmpty) return op;
    }
    for (final op in stop.opinions) {
      if (op.demosAndMeanings.isNotEmpty) return op;
    }
    return null;
  }

  /// Current position among swipeable demos: (stopIndex, demoIndex), or null.
  (int, int)? get demoNavPosition {
    if (!demoHighlightActive || selectedStopId == null) return null;
    final stops = demoNavStops;
    final stopIdx = stops.indexWhere((s) => s.id == selectedStopId);
    if (stopIdx < 0) return null;
    final op = _demoOpinionFor(stops[stopIdx]);
    if (op == null || op.demosAndMeanings.isEmpty) return null;
    final demoIdx =
        (selectedDemoIndex ?? 0).clamp(0, op.demosAndMeanings.length - 1);
    return (stopIdx, demoIdx);
  }

  /// Total flat demo count for the «١ / ن» indicator.
  int get demoNavTotalCount {
    var n = 0;
    for (final s in demoNavStops) {
      final op = _demoOpinionFor(s);
      if (op != null) n += op.demosAndMeanings.length;
    }
    return n;
  }

  /// 1-based flat index of the active demo, or 0 if none.
  int get demoNavFlatIndex {
    final pos = demoNavPosition;
    if (pos == null) return 0;
    final stops = demoNavStops;
    var flat = 0;
    for (var i = 0; i < pos.$1; i++) {
      final op = _demoOpinionFor(stops[i]);
      if (op != null) flat += op.demosAndMeanings.length;
    }
    return flat + pos.$2 + 1;
  }

  /// Step to next/prev demo. Cycles demos on the same stop first, then adjacent stops.
  /// [delta] > 0 = next in reading order; < 0 = previous. Returns false at ends.
  bool stepDemo(int delta) {
    if (delta == 0 || !demoHighlightActive) return false;
    final stops = demoNavStops;
    if (stops.isEmpty) return false;

    final pos = demoNavPosition;
    if (pos == null) {
      final first = stops.first;
      final op = _demoOpinionFor(first);
      if (op == null) return false;
      activateDemoHighlight(first.id, scholar: op.scholar, demoIndex: 0);
      return true;
    }

    var stopIdx = pos.$1;
    var demoIdx = pos.$2;
    final step = delta > 0 ? 1 : -1;
    var remaining = delta.abs();

    while (remaining > 0) {
      final op = _demoOpinionFor(stops[stopIdx]);
      final demoCount = op?.demosAndMeanings.length ?? 0;
      final nextDemo = demoIdx + step;
      if (nextDemo >= 0 && nextDemo < demoCount) {
        demoIdx = nextDemo;
        remaining -= 1;
        continue;
      }
      final nextStop = stopIdx + step;
      if (nextStop < 0 || nextStop >= stops.length) {
        return false;
      }
      stopIdx = nextStop;
      final nextOp = _demoOpinionFor(stops[stopIdx]);
      final nextCount = nextOp?.demosAndMeanings.length ?? 0;
      if (nextCount == 0) return false;
      demoIdx = step > 0 ? 0 : nextCount - 1;
      remaining -= 1;
    }

    final target = stops[stopIdx];
    final targetOp = _demoOpinionFor(target);
    if (targetOp == null) return false;
    activateDemoHighlight(
      target.id,
      scholar: targetOp.scholar,
      demoIndex: demoIdx,
    );
    return true;
  }

  /// Active demo used for mushaf span highlighting for the selected stop.
  WaqfDemoAndMeaning? get activeDemoHighlight {
    if (!demoHighlightActive) return null;
    final stop = selectedStopId == null ? null : stopById(selectedStopId!);
    if (stop == null) return null;

    ScholarOpinion? preferred;
    final demoScholar = selectedDemoScholar ?? selectedScholar;
    if (demoScholar != null && demoScholar.isNotEmpty) {
      final op = stop.opinionForScholar(demoScholar);
      if (op != null && op.demosAndMeanings.isNotEmpty) preferred = op;
    }
    if (preferred == null) {
      for (final op in stop.opinions) {
        if (op.demosAndMeanings.isNotEmpty) {
          preferred = op;
          break;
        }
      }
    }
    if (preferred == null || preferred.demosAndMeanings.isEmpty) return null;

    final demos = preferred.demosAndMeanings;
    final idx = (selectedDemoIndex ?? 0).clamp(0, demos.length - 1);
    return demos[idx];
  }

  DemoSegmentRole demoRoleForWord({
    required int ayahNumber,
    required int wordIndex,
  }) {
    final stop = selectedStopId == null ? null : stopById(selectedStopId!);
    if (stop == null || stop.ayah != ayahNumber) return DemoSegmentRole.none;
    return demoSegmentRoleForWord(
      demo: activeDemoHighlight,
      wordIndex: wordIndex,
    );
  }

  Future<void> markForReview(String id) async {
    if (sentToReview.add(id)) {
      notifyListeners();
      final stop = _stopsById[id];
      if (stop != null) {
        unawaited(
          WaqfReportService.submitStopReport(
            stop: stop,
            surahName: currentSurahName,
            flagged: true,
            scholarFilter: selectedScholar,
          ),
        );
      }
      await _persistPrefs();
    }
  }

  Future<void> toggleSent(String id) async {
    final added = sentToReview.add(id);
    if (!added) {
      sentToReview.remove(id);
    }
    notifyListeners();
    final stop = _stopsById[id];
    if (stop != null) {
      unawaited(
        WaqfReportService.submitStopReport(
          stop: stop,
          surahName: currentSurahName,
          flagged: added,
          scholarFilter: selectedScholar,
        ),
      );
    }
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
    if (filter == ReviewListFilter.all) {
      return List<WaqfStop>.from(sampleStops);
    }
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
