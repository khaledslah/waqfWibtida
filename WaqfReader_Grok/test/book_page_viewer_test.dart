import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:waqf_reader_grok/data/sample_data.dart';
import 'package:waqf_reader_grok/main.dart';
import 'package:waqf_reader_grok/models/waqf_models.dart';
import 'package:waqf_reader_grok/screens/review_screen.dart';
import 'package:waqf_reader_grok/theme/app_theme.dart';
import 'package:waqf_reader_grok/utils/book_page_service.dart';
import 'package:waqf_reader_grok/widgets/page_image_viewer.dart';

// Valid 1x1 transparent PNG
const _kSamplePngB64 =
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';
final Uint8List _kSamplePngBytes = base64Decode(_kSamplePngB64);

BookPageRecord _makeRecord({
  required String bookKey,
  required int pageNum,
  int vol = 1,
  int totalPages = 500,
  String? pageText,
}) {
  final meta = kBookDisplayMeta[bookKey]!;
  return BookPageRecord(
    bookKey: bookKey,
    scholarAr: meta.scholarAr,
    titleAr: meta.titleAr,
    editionAr: meta.editionAr,
    totalPages: totalPages,
    vol: vol,
    pageNum: pageNum,
    seqIndex: pageNum,
    imageBytes: _kSamplePngBytes,
    width: 960,
    height: 1400,
    pageText: pageText,
  );
}

void main() {
  setUpAll(() {
    GoogleFonts.config.allowRuntimeFetching = false;
    SharedPreferences.setMockInitialValues(<String, Object>{});
  });

  tearDown(() {
    BookPageService.debugFetcher = null;
    BookPageService.clearCache();
  });

  group('BookPageRef & scholar book mapping', () {
    test('BookPageRef.parse handles all feed formats cleanly', () {
      final p1 = BookPageRef.parse('1/173-179')!;
      expect(p1.volume, 1);
      expect(p1.page, 173);
      expect(p1.endPage, 179);
      expect(p1.isAyahRef, isFalse);

      final p2 = BookPageRef.parse('3/853 - 3/854')!;
      expect(p2.volume, 3);
      expect(p2.page, 853);
      expect(p2.endPage, 854);

      final p3 = BookPageRef.parse('1027-1029/3')!;
      expect(p3.volume, 3);
      expect(p3.page, 1027);
      expect(p3.endPage, 1029);

      final p4 = BookPageRef.parse('753 - 2/754')!;
      expect(p4.volume, 2);
      expect(p4.page, 753);
      expect(p4.endPage, 754);

      final p5 = BookPageRef.parse('474-476')!;
      expect(p5.volume, isNull);
      expect(p5.page, 474);
      expect(p5.endPage, 476);

      final pAr = BookPageRef.parse('١/١٧٣-١٧٩')!;
      expect(pAr.volume, 1);
      expect(pAr.page, 173);
      expect(pAr.endPage, 179);

      final ay1 = BookPageRef.parse('آية 258')!;
      expect(ay1.isAyahRef, isTrue);
      expect(ay1.ayahNumber, 258);
      expect(ay1.page, isNull);

      final ay2 = BookPageRef.parse('آية 273 - 275')!;
      expect(ay2.isAyahRef, isTrue);
      expect(ay2.ayahNumber, 273);

      expect(parsePageNumber('1027-1029/3'), 1027);
      expect(parsePageNumber('آية ٢٥٨'), isNull);
      expect(BookPageRef.parse(''), isNull);
      expect(BookPageRef.parse(null), isNull);
    });

    test('bookKeyForScholar maps all 5 classical scholars and books', () {
      expect(
        bookKeyForScholar(scholar: 'السجاوندي', book: 'علل الوقوف'),
        'sajawandi',
      );
      expect(
        bookKeyForScholar(scholar: 'ابن الأنباري', book: 'إيضاح الوقف والابتداء'),
        'anbari',
      );
      expect(
        bookKeyForScholar(scholar: 'الداني', book: 'المكتفى'),
        'dani',
      );
      expect(
        bookKeyForScholar(scholar: 'الأشموني', book: 'منار الهدى'),
        'ashmuni',
      );
      expect(
        bookKeyForScholar(scholar: 'النحاس', book: 'القطع والائتناف'),
        'nahhas',
      );
      expect(bookKeyForScholar(scholar: 'غير معروف', book: 'كتاب آخر'), isNull);
    });

    test('BookPageRecord.fromNeonRow strips PostgreSQL base64 newlines', () {
      final multilineB64 = '${_kSamplePngB64.substring(0, 40)}\n${_kSamplePngB64.substring(40)}\r\n';
      final rec = BookPageRecord.fromNeonRow(<String, dynamic>{
        'book_key': 'nahhas',
        'scholar_ar': 'النحاس',
        'title_ar': 'القطع والائتناف',
        'edition_ar': 'تحقيق المطرودي',
        'total_pages': '836',
        'vol': 1,
        'page_num': 108,
        'seq_index': 108,
        'width': '960',
        'height': 1400,
        'image_b64': multilineB64,
        'page_text': 'قوله تعالى الله لا إله إلا هو الحي القيوم',
      });
      expect(rec.totalPages, 836);
      expect(rec.width, 960);
      expect(rec.imageBytes, _kSamplePngBytes);
      expect(rec.hasPageText, isTrue);
    });

    test('BookPageService caches pages and routes ayah anchors', () async {
      var calls = 0;
      BookPageService.debugFetcher = (q) async {
        calls++;
        if (q.type == BookPageQueryType.byAyah) {
          expect(q.bookKey, 'nahhas');
          expect(q.surah, 2);
          expect(q.ayah, 258);
          return _makeRecord(
            bookKey: 'nahhas',
            pageNum: 108,
            totalPages: 836,
            pageText: 'نص النحاس',
          );
        }
        return _makeRecord(
          bookKey: q.bookKey,
          pageNum: q.pageNum ?? 1,
          vol: q.vol ?? 1,
          totalPages: 1218,
        );
      };

      final rec1 = await BookPageService.fetchForOpinion(
        scholar: 'النحاس',
        book: 'القطع والائتناف',
        pageStr: 'آية 258',
        surah: 2,
        ayah: 258,
      );
      expect(rec1?.pageNum, 108);
      expect(calls, 1);

      // Second lookup for same anchor hits LRU cache
      final rec2 = await BookPageService.fetchByAyah(
        bookKey: 'nahhas',
        surah: 2,
        ayah: 258,
      );
      expect(rec2?.pageNum, 108);
      expect(calls, 1);
    });
  });

  group('BookPageViewerDialog widget tests', () {
    Widget wrapHost(Widget Function(BuildContext ctx) builder) {
      return MaterialApp(
        theme: AppTheme.light(),
        home: Directionality(
          textDirection: TextDirection.rtl,
          child: Scaffold(
            body: Builder(builder: builder),
          ),
        ),
      );
    }

    testWidgets(
      'displays image, toggles Shamela text, and navigates Prev/Next via LRU cache',
      (tester) async {
        var fetchCalls = 0;
        BookPageService.debugFetcher = (q) async {
          fetchCalls++;
          final target = q.type == BookPageQueryType.bySeq
              ? q.seqIndex!
              : (q.pageNum ?? 1);
          return _makeRecord(
            bookKey: q.bookKey,
            pageNum: target,
            vol: target >= 561 ? 2 : 1,
            totalPages: 1199,
            pageText: 'نص إيضاح الوقف والابتداء صفحة $target',
          );
        };

        await tester.pumpWidget(
          wrapHost(
            (ctx) => ElevatedButton(
              onPressed: () => showScholarBookPage(
                ctx,
                scholar: 'ابن الأنباري',
                book: 'إيضاح الوقف والابتداء',
                pageStr: '474-476',
                surah: 2,
                ayah: 100,
              ),
              child: const Text('فتح'),
            ),
          ),
        );

        await tester.tap(find.text('فتح'));
        await tester.pumpAndSettle();

        expect(find.text('إيضاح الوقف والابتداء'), findsOneWidget);
        expect(find.textContaining('٤٧٤ / ١١٩٩'), findsOneWidget);
        expect(find.byType(Image), findsOneWidget);
        expect(find.text('النص الرقمي'), findsOneWidget);
        expect(fetchCalls, 1);

        // Toggle to digital text
        await tester.tap(find.text('النص الرقمي'));
        await tester.pumpAndSettle();
        expect(find.text('نص إيضاح الوقف والابتداء صفحة 474'), findsOneWidget);
        expect(find.byTooltip('نسخ نص الصفحة'), findsOneWidget);

        // Navigate Next -> page 475
        await tester.tap(find.text('التالية'));
        await tester.pumpAndSettle();
        expect(find.textContaining('٤٧٥ / ١١٩٩'), findsOneWidget);
        expect(find.text('نص إيضاح الوقف والابتداء صفحة 475'), findsOneWidget);
        expect(fetchCalls, 2);

        // Toggle back to image
        await tester.tap(find.text('صورة الصفحة'));
        await tester.pumpAndSettle();
        expect(find.byType(Image), findsOneWidget);

        // Navigate Prev -> page 474 (cached!)
        await tester.tap(find.text('السابقة'));
        await tester.pumpAndSettle();
        expect(find.textContaining('٤٧٤ / ١١٩٩'), findsOneWidget);
        expect(fetchCalls, 2);
      },
    );

    testWidgets(
      'hides digital text button for image-only books (Ashmuni/Dani)',
      (tester) async {
        BookPageService.debugFetcher = (q) async => _makeRecord(
              bookKey: 'ashmuni',
              pageNum: q.pageNum ?? 35,
              totalPages: 448,
              pageText: null,
            );

        await tester.pumpWidget(
          wrapHost(
            (ctx) => ElevatedButton(
              onPressed: () => showScholarBookPage(
                ctx,
                scholar: 'الأشموني',
                book: 'منار الهدى',
                pageStr: '35',
              ),
              child: const Text('فتح الأشموني'),
            ),
          ),
        );

        await tester.tap(find.text('فتح الأشموني'));
        await tester.pumpAndSettle();

        expect(find.text('منار الهدى في بيان الوقف والابتدا'), findsOneWidget);
        expect(find.textContaining('٣٥ / ٤٤٨'), findsOneWidget);
        expect(find.text('النص الرقمي'), findsNothing);
        expect(find.byType(Image), findsOneWidget);
      },
    );

    testWidgets(
      'resolves Al-Nahhas ayah reference and supports error retry',
      (tester) async {
        var shouldFail = true;
        BookPageService.debugFetcher = (q) async {
          if (shouldFail) {
            throw const BookPageFetchException('تعذّر الاتصال مؤقتاً');
          }
          expect(q.type, BookPageQueryType.byAyah);
          expect(q.bookKey, 'nahhas');
          expect(q.surah, 2);
          expect(q.ayah, 258);
          return _makeRecord(
            bookKey: 'nahhas',
            pageNum: 108,
            totalPages: 836,
            pageText: 'نص سورة البقرة آية ٢٥٨',
          );
        };

        await tester.pumpWidget(
          wrapHost(
            (ctx) => ElevatedButton(
              onPressed: () => showScholarBookPage(
                ctx,
                scholar: 'النحاس',
                book: 'القطع والائتناف',
                pageStr: 'آية 258',
                surah: 2,
                ayah: 258,
              ),
              child: const Text('فتح النحاس'),
            ),
          ),
        );

        await tester.tap(find.text('فتح النحاس'));
        await tester.pumpAndSettle();

        expect(find.text('تعذّر الاتصال مؤقتاً'), findsOneWidget);
        expect(find.text('إعادة المحاولة'), findsOneWidget);

        shouldFail = false;
        await tester.tap(find.text('إعادة المحاولة'));
        await tester.pumpAndSettle();

        expect(find.text('القطع والائتناف'), findsOneWidget);
        expect(find.textContaining('١٠٨ / ٨٣٦'), findsOneWidget);
      },
    );

    testWidgets(
      'tapping non-Sajawandi book reference inside WaqfBottomSheet opens Neon viewer',
      (tester) async {
        tester.view.physicalSize = const Size(390, 844);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        BookPageQuery? capturedQuery;
        BookPageService.debugFetcher = (q) async {
          capturedQuery = q;
          return _makeRecord(
            bookKey: q.bookKey,
            pageNum: q.pageNum ?? 474,
            vol: q.vol ?? 1,
            totalPages: 1199,
            pageText: 'والوقف على الرحيم تام',
          );
        };

        await tester.pumpWidget(const WaqfReaderApp());
        await tester.pump();
        var loaded = false;
        for (var i = 0; i < 100; i++) {
          await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 20)),
          );
          await tester.pump(const Duration(milliseconds: 50));
          if (find.text('إخفاء رؤوس الآي').evaluate().isNotEmpty) {
            await tester.pump();
            loaded = true;
            break;
          }
        }
        if (!loaded) {
          final texts = find
              .byType(Text)
              .evaluate()
              .map((e) => (e.widget as Text).data)
              .toList();
          fail('Not loaded; found texts: $texts, spinners: ${find.byType(CircularProgressIndicator).evaluate().length}');
        }

        // Turn off 'إخفاء رؤوس الآي' so verse-end stop on s1-a1-w4 (الرحيم) is visible
        await tester.tap(find.text('إخفاء رؤوس الآي'));
        await tester.pumpAndSettle();

        // Tap first stop badge on الفاتحة (s1-a1-w4 has ابن الأنباري 1/474, الداني 155, الأشموني 28)
        final firstBadge = find.byType(InkResponse).first;
        await tester.tap(firstBadge);
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));

        // Tap Ibn Al-Anbari ref ('1/474') inside WaqfBottomSheet
        final anbariRef = find.text('1/474');
        expect(anbariRef, findsOneWidget);
        await tester.ensureVisible(anbariRef);
        await tester.tap(anbariRef);
        await tester.pumpAndSettle();

        expect(capturedQuery?.bookKey, 'anbari');
        expect(capturedQuery?.pageNum, 474);
        expect(capturedQuery?.vol, 1);
        expect(find.byType(BookPageViewerDialog), findsOneWidget);
        expect(
          find.descendant(
            of: find.byType(BookPageViewerDialog),
            matching: find.text('إيضاح الوقف والابتداء'),
          ),
          findsOneWidget,
        );
        expect(
          find.descendant(
            of: find.byType(BookPageViewerDialog),
            matching: find.textContaining('٤٧٤ / ١١٩٩'),
          ),
          findsOneWidget,
        );
      },
    );

    testWidgets(
      'ReviewScreen page button opens selected scholar book page',
      (tester) async {
        tester.view.physicalSize = const Size(390, 844);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        BookPageQuery? capturedQuery;
        BookPageService.debugFetcher = (q) async {
          capturedQuery = q;
          return _makeRecord(
            bookKey: q.bookKey,
            pageNum: q.pageNum ?? 28,
            totalPages: 448,
          );
        };

        final controller = ReaderController();
        addTearDown(controller.dispose);
        final bundle = await tester.runAsync(
          () => AppFeedBundle.loadAsset('app_feed/surah_001.json'),
        );
        controller.sampleStops = bundle!.stops;
        controller.yusufAyahs = bundle.ayahs;
        controller.currentSurah = bundle.surah;
        controller.currentSurahName = bundle.surahName;
        controller.loadState = ReaderLoadState.ready;
        controller.setSelectedScholar('الأشموني');

        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light(),
            home: Directionality(
              textDirection: TextDirection.rtl,
              child: Scaffold(
                body: ReviewScreen(controller: controller),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();

        // Find page button "28" on a fatiha stop card in ReviewScreen
        final pageBtn = find.text('28').first;
        await tester.ensureVisible(pageBtn);
        await tester.tap(pageBtn);
        await tester.pumpAndSettle();

        expect(capturedQuery?.bookKey, 'ashmuni');
        expect(capturedQuery?.pageNum, 28);
        expect(find.byType(BookPageViewerDialog), findsOneWidget);
        expect(
          find.descendant(
            of: find.byType(BookPageViewerDialog),
            matching: find.text('منار الهدى في بيان الوقف والابتدا'),
          ),
          findsOneWidget,
        );
      },
    );
  });
}
