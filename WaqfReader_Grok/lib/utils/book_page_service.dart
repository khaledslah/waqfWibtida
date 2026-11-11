import 'dart:async';
import 'dart:collection';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../models/waqf_models.dart';
import 'report_service.dart';

/// Maps a scholar name and/or book title from `app_feed` onto its Neon `book_key`.
String? bookKeyForScholar({
  required String scholar,
  String? book,
}) {
  final s = scholar.trim();
  final b = (book ?? '').trim();
  if (s == 'sajawandi' ||
      s.contains('سجاوندي') ||
      b.contains('علل الوقوف')) {
    return 'sajawandi';
  }
  if (s == 'anbari' ||
      s.contains('أنباري') ||
      s.contains('انباري') ||
      b.contains('إيضاح')) {
    return 'anbari';
  }
  if (s == 'dani' || s.contains('داني') || b.contains('المكتفى')) {
    return 'dani';
  }
  if (s == 'ashmuni' ||
      s.contains('أشموني') ||
      s.contains('اشموني') ||
      b.contains('منار الهدى')) {
    return 'ashmuni';
  }
  if (s == 'nahhas' ||
      s.contains('نحاس') ||
      b.contains('القطع والائتناف')) {
    return 'nahhas';
  }
  return null;
}

class BookDisplayMeta {
  const BookDisplayMeta({
    required this.bookKey,
    required this.scholarAr,
    required this.titleAr,
    required this.editionAr,
  });

  final String bookKey;
  final String scholarAr;
  final String titleAr;
  final String editionAr;
}

const Map<String, BookDisplayMeta> kBookDisplayMeta = <String, BookDisplayMeta>{
  'sajawandi': BookDisplayMeta(
    bookKey: 'sajawandi',
    scholarAr: 'السجاوندي',
    titleAr: 'علل الوقوف',
    editionAr: 'تحقيق د. محمد العيدي · مكتبة الرشد',
  ),
  'anbari': BookDisplayMeta(
    bookKey: 'anbari',
    scholarAr: 'ابن الأنباري',
    titleAr: 'إيضاح الوقف والابتداء',
    editionAr: 'تحقيق د. محيي الدين رمضان · مجمع اللغة العربية بدمشق',
  ),
  'dani': BookDisplayMeta(
    bookKey: 'dani',
    scholarAr: 'الداني',
    titleAr: 'المكتفى في الوقف والابتدا',
    editionAr: 'تحقيق د. يوسف المرعشلي · مؤسسة الرسالة',
  ),
  'ashmuni': BookDisplayMeta(
    bookKey: 'ashmuni',
    scholarAr: 'الأشموني',
    titleAr: 'منار الهدى في بيان الوقف والابتدا',
    editionAr: 'مطبعة مصطفى البابي الحلبي · القاهرة ١٩٧٣م',
  ),
  'nahhas': BookDisplayMeta(
    bookKey: 'nahhas',
    scholarAr: 'النحاس',
    titleAr: 'القطع والائتناف',
    editionAr: 'تحقيق د. عبد الرحمن المطرودي · دار عالم الكتب',
  ),
};

enum BookPageQueryType { byPage, bySeq, byAyah }

class BookPageQuery {
  const BookPageQuery.byPage({
    required this.bookKey,
    required this.pageNum,
    this.vol,
  })  : type = BookPageQueryType.byPage,
        seqIndex = null,
        surah = null,
        ayah = null;

  const BookPageQuery.bySeq({
    required this.bookKey,
    required this.seqIndex,
  })  : type = BookPageQueryType.bySeq,
        pageNum = null,
        vol = null,
        surah = null,
        ayah = null;

  const BookPageQuery.byAyah({
    required this.bookKey,
    required this.surah,
    required this.ayah,
  })  : type = BookPageQueryType.byAyah,
        pageNum = null,
        vol = null,
        seqIndex = null;

  final BookPageQueryType type;
  final String bookKey;
  final int? pageNum;
  final int? vol;
  final int? seqIndex;
  final int? surah;
  final int? ayah;
}

class BookPageFetchException implements Exception {
  const BookPageFetchException(this.message);

  final String message;

  @override
  String toString() => message;
}

class BookPageRecord {
  const BookPageRecord({
    required this.bookKey,
    required this.scholarAr,
    required this.titleAr,
    required this.editionAr,
    required this.totalPages,
    required this.vol,
    required this.pageNum,
    required this.seqIndex,
    required this.imageBytes,
    this.width,
    this.height,
    this.pageText,
  });

  final String bookKey;
  final String scholarAr;
  final String titleAr;
  final String editionAr;
  final int totalPages;
  final int vol;
  final int pageNum;
  final int seqIndex;
  final Uint8List imageBytes;
  final int? width;
  final int? height;
  final String? pageText;

  bool get hasPageText => pageText != null && pageText!.trim().isNotEmpty;

  static int? _asInt(dynamic raw) {
    if (raw == null) return null;
    if (raw is int) return raw;
    if (raw is num) return raw.toInt();
    return int.tryParse(raw.toString());
  }

  factory BookPageRecord.fromNeonRow(Map<String, dynamic> row) {
    final rawB64 = (row['image_b64']?.toString() ?? '')
        .replaceAll(RegExp(r'\s+'), '');
    final bytes = rawB64.isEmpty ? Uint8List(0) : base64Decode(rawB64);
    final rawText = row['page_text']?.toString();
    return BookPageRecord(
      bookKey: row['book_key']?.toString() ?? '',
      scholarAr: row['scholar_ar']?.toString() ?? '',
      titleAr: row['title_ar']?.toString() ?? '',
      editionAr: row['edition_ar']?.toString() ?? '',
      totalPages: _asInt(row['total_pages']) ?? 1,
      vol: _asInt(row['vol']) ?? 1,
      pageNum: _asInt(row['page_num']) ?? 1,
      seqIndex: _asInt(row['seq_index']) ?? 1,
      width: _asInt(row['width']),
      height: _asInt(row['height']),
      imageBytes: bytes,
      pageText: (rawText != null && rawText.trim().isNotEmpty) ? rawText : null,
    );
  }
}

typedef BookPageDebugFetcher = Future<BookPageRecord?> Function(
  BookPageQuery query,
);

/// Fetches scanned book pages and Shamela transcriptions from Neon Serverless Postgres
/// over HTTP `/sql` (compatible with Flutter Web, Android, iOS, and desktop).
class BookPageService {
  static const int _maxCacheEntries = 30;
  static final http.Client _httpClient = http.Client();

  static final LinkedHashMap<String, BookPageRecord> _seqCache =
      LinkedHashMap<String, BookPageRecord>();
  static final Map<String, String> _pageIndex = <String, String>{};
  static final Map<String, String> _anchorIndex = <String, String>{};
  static final Map<String, Future<BookPageRecord?>> _inflight =
      <String, Future<BookPageRecord?>>{};

  /// Test hook to stub Neon fetches cleanly during widget/unit tests.
  @visibleForTesting
  static BookPageDebugFetcher? debugFetcher;

  @visibleForTesting
  static void clearCache() {
    _seqCache.clear();
    _pageIndex.clear();
    _anchorIndex.clear();
    _inflight.clear();
  }

  static BookPageRecord? _touchSeqCache(String seqKey) {
    final existing = _seqCache.remove(seqKey);
    if (existing != null) {
      _seqCache[seqKey] = existing;
    }
    return existing;
  }

  static void _remember(
    BookPageRecord rec, {
    String? requestedPageKey,
    String? requestedAnchorKey,
  }) {
    final seqKey = '${rec.bookKey}:seq:${rec.seqIndex}';
    _seqCache.remove(seqKey);
    _seqCache[seqKey] = rec;

    _pageIndex['${rec.bookKey}:p:${rec.vol}:${rec.pageNum}'] = seqKey;
    _pageIndex['${rec.bookKey}:pAny:${rec.pageNum}'] = seqKey;
    if (requestedPageKey != null) {
      _pageIndex[requestedPageKey] = seqKey;
    }
    if (requestedAnchorKey != null) {
      _anchorIndex[requestedAnchorKey] = seqKey;
    }

    while (_seqCache.length > _maxCacheEntries) {
      final oldestKey = _seqCache.keys.first;
      _seqCache.remove(oldestKey);
      _pageIndex.removeWhere((_, v) => v == oldestKey);
      _anchorIndex.removeWhere((_, v) => v == oldestKey);
    }
  }

  static Future<BookPageRecord?> fetchForOpinion({
    required String scholar,
    required String book,
    required String? pageStr,
    int? sajawandiPage,
    int? surah,
    int? ayah,
  }) async {
    final bookKey = bookKeyForScholar(scholar: scholar, book: book);
    if (bookKey == null) return null;

    final ref = BookPageRef.parse(pageStr);
    if (ref != null && ref.page != null) {
      return fetchByPage(
        bookKey: bookKey,
        pageNum: ref.page!,
        vol: ref.volume,
      );
    }

    if (bookKey == 'sajawandi' && sajawandiPage != null) {
      return fetchByPage(bookKey: bookKey, pageNum: sajawandiPage);
    }

    if (surah != null && (ref?.ayahNumber != null || ayah != null)) {
      return fetchByAyah(
        bookKey: bookKey,
        surah: surah,
        ayah: ref?.ayahNumber ?? ayah!,
      );
    }

    return null;
  }

  static Future<BookPageRecord?> fetchByPage({
    required String bookKey,
    required int pageNum,
    int? vol,
  }) {
    final lookupKey =
        vol != null ? '$bookKey:p:$vol:$pageNum' : '$bookKey:pAny:$pageNum';
    final cachedSeqKey = _pageIndex[lookupKey];
    if (cachedSeqKey != null) {
      final cached = _touchSeqCache(cachedSeqKey);
      if (cached != null) return SynchronousFuture<BookPageRecord?>(cached);
    }

    final query = BookPageQuery.byPage(
      bookKey: bookKey,
      pageNum: pageNum,
      vol: vol,
    );
    return _coalescedFetch(
      inflightKey: 'page:$lookupKey',
      query: query,
      requestedPageKey: lookupKey,
    );
  }

  static Future<BookPageRecord?> fetchBySeq({
    required String bookKey,
    required int seqIndex,
  }) {
    final seqKey = '$bookKey:seq:$seqIndex';
    final cached = _touchSeqCache(seqKey);
    if (cached != null) return SynchronousFuture<BookPageRecord?>(cached);

    return _coalescedFetch(
      inflightKey: 'seq:$seqKey',
      query: BookPageQuery.bySeq(bookKey: bookKey, seqIndex: seqIndex),
    );
  }

  static Future<BookPageRecord?> fetchByAyah({
    required String bookKey,
    required int surah,
    required int ayah,
  }) {
    final anchorKey = '$bookKey:a:$surah:$ayah';
    final cachedSeqKey = _anchorIndex[anchorKey];
    if (cachedSeqKey != null) {
      final cached = _touchSeqCache(cachedSeqKey);
      if (cached != null) return SynchronousFuture<BookPageRecord?>(cached);
    }

    return _coalescedFetch(
      inflightKey: 'anchor:$anchorKey',
      query: BookPageQuery.byAyah(
        bookKey: bookKey,
        surah: surah,
        ayah: ayah,
      ),
      requestedAnchorKey: anchorKey,
    );
  }

  static Future<BookPageRecord?> _coalescedFetch({
    required String inflightKey,
    required BookPageQuery query,
    String? requestedPageKey,
    String? requestedAnchorKey,
  }) {
    final existing = _inflight[inflightKey];
    if (existing != null) return existing;

    final future = () async {
      try {
        final rec = await _executeQuery(query);
        if (rec != null) {
          _remember(
            rec,
            requestedPageKey: requestedPageKey,
            requestedAnchorKey: requestedAnchorKey,
          );
        }
        return rec;
      } finally {
        _inflight.remove(inflightKey);
      }
    }();

    _inflight[inflightKey] = future;
    return future;
  }

  static Future<BookPageRecord?> _executeQuery(BookPageQuery query) async {
    final stub = debugFetcher;
    if (stub != null) {
      return stub(query);
    }

    if (!ReportCloudConfig.hasNeon) {
      throw const BookPageFetchException('إعدادات الاتصال بقاعدة الكتب غير متوفرة.');
    }

    late final String sql;
    late final List<dynamic> params;

    switch (query.type) {
      case BookPageQueryType.byPage:
        if (query.vol != null) {
          sql = '''
SELECT p.book_key, b.scholar_ar, b.title_ar, b.edition_ar, b.total_pages,
       p.vol, p.page_num, p.seq_index, p.width, p.height,
       encode(p.image_data, 'base64') AS image_b64,
       p.page_text
FROM book_pages p
JOIN books b ON b.book_key = p.book_key
WHERE p.book_key = \$1 AND p.page_num = \$2
ORDER BY CASE WHEN p.vol = \$3 THEN 0 ELSE 1 END, p.vol ASC
LIMIT 1
''';
          params = <dynamic>[query.bookKey, query.pageNum, query.vol];
        } else {
          sql = '''
SELECT p.book_key, b.scholar_ar, b.title_ar, b.edition_ar, b.total_pages,
       p.vol, p.page_num, p.seq_index, p.width, p.height,
       encode(p.image_data, 'base64') AS image_b64,
       p.page_text
FROM book_pages p
JOIN books b ON b.book_key = p.book_key
WHERE p.book_key = \$1 AND p.page_num = \$2
ORDER BY p.vol ASC
LIMIT 1
''';
          params = <dynamic>[query.bookKey, query.pageNum];
        }
      case BookPageQueryType.bySeq:
        sql = '''
SELECT p.book_key, b.scholar_ar, b.title_ar, b.edition_ar, b.total_pages,
       p.vol, p.page_num, p.seq_index, p.width, p.height,
       encode(p.image_data, 'base64') AS image_b64,
       p.page_text
FROM book_pages p
JOIN books b ON b.book_key = p.book_key
WHERE p.book_key = \$1 AND p.seq_index = \$2
LIMIT 1
''';
        params = <dynamic>[query.bookKey, query.seqIndex];
      case BookPageQueryType.byAyah:
        sql = '''
SELECT p.book_key, b.scholar_ar, b.title_ar, b.edition_ar, b.total_pages,
       p.vol, p.page_num, p.seq_index, p.width, p.height,
       encode(p.image_data, 'base64') AS image_b64,
       p.page_text
FROM book_ayah_anchors a
JOIN book_pages p
  ON p.book_key = a.book_key AND p.vol = a.vol AND p.page_num = a.page_num
JOIN books b ON b.book_key = p.book_key
WHERE a.book_key = \$1 AND a.surah = \$2
ORDER BY (CASE WHEN a.ayah <= \$3 THEN 0 ELSE 1 END), ABS(a.ayah - \$3) ASC
LIMIT 1
''';
        params = <dynamic>[query.bookKey, query.surah, query.ayah];
    }

    try {
      final res = await _httpClient
          .post(
            Uri.parse(ReportCloudConfig.neonHttpSqlUrl.trim()),
            headers: <String, String>{
              'Neon-Connection-String':
                  ReportCloudConfig.neonConnectionString.trim(),
              // Use text/plain so Flutter Web CORS preflight succeeds cleanly
              'Content-Type': 'text/plain; charset=utf-8',
            },
            body: jsonEncode(<String, dynamic>{
              'query': sql,
              'params': params,
            }),
          )
          .timeout(const Duration(seconds: 20));

      if (res.statusCode != 200) {
        throw BookPageFetchException(
          'تعذّر تحميل الصفحة من الخادم (HTTP ${res.statusCode}).',
        );
      }

      final decoded = jsonDecode(utf8.decode(res.bodyBytes));
      if (decoded is! Map<String, dynamic>) {
        throw const BookPageFetchException('استجابة غير متوقعة من الخادم.');
      }
      final rows = decoded['rows'] as List<dynamic>? ?? const <dynamic>[];
      if (rows.isEmpty) {
        return null;
      }
      final first = rows.first;
      if (first is! Map<String, dynamic>) {
        return null;
      }
      return BookPageRecord.fromNeonRow(first);
    } on BookPageFetchException {
      rethrow;
    } on TimeoutException {
      throw const BookPageFetchException(
        'انتهت مهلة الاتصال أثناء تحميل الصفحة، يرجى المحاولة مرة أخرى.',
      );
    } catch (_) {
      throw const BookPageFetchException(
        'تعذّر تحميل الصفحة، تأكد من اتصالك بالإنترنت ثم أعد المحاولة.',
      );
    }
  }
}
