import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/waqf_models.dart';
import '../theme/app_theme.dart';
import '../utils/book_page_service.dart';

/// Opens the scanned classical book page dialog for any of the 5 supported scholars/books.
///
/// Works worldwide via Neon Serverless Postgres (`books`, `book_pages`, `book_ayah_anchors`)
/// on Flutter Web, Android, iOS, and desktop without any local Python image server.
Future<void> showScholarBookPage(
  BuildContext context, {
  required String scholar,
  required String book,
  required String? pageStr,
  int? sajawandiPage,
  int? surah,
  int? ayah,
}) {
  final bookKey = bookKeyForScholar(scholar: scholar, book: book);
  if (bookKey == null) {
    ScaffoldMessenger.maybeOf(context)?.showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 3),
        content: Text(
          'لا تتوفر صفحات مصوّرة لكتاب «$book» حالياً.',
          style: AppText.ui(size: 13, color: AppColors.white),
        ),
      ),
    );
    return Future.value();
  }

  final ref = BookPageRef.parse(pageStr);
  final targetPage =
      ref?.page ?? (bookKey == 'sajawandi' ? sajawandiPage : null);
  final targetAyah = ref?.ayahNumber ?? ayah;
  final canResolveByAyah =
      targetPage == null && surah != null && targetAyah != null;

  if (targetPage == null && !canResolveByAyah) {
    ScaffoldMessenger.maybeOf(context)?.showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 3),
        content: Text(
          'لا يوجد رقم صفحة متاح لهذا القول في «$book».',
          style: AppText.ui(size: 13, color: AppColors.white),
        ),
      ),
    );
    return Future.value();
  }

  final meta = kBookDisplayMeta[bookKey];
  return showDialog<void>(
    context: context,
    barrierColor: const Color(0xCC000000),
    builder: (context) {
      return BookPageViewerDialog(
        bookKey: bookKey,
        initialScholar: scholar.isNotEmpty ? scholar : (meta?.scholarAr ?? ''),
        initialBookTitle: book.isNotEmpty ? book : (meta?.titleAr ?? ''),
        initialPageRef: pageStr,
        initialPageNum: targetPage,
        initialVol: ref?.volume,
        surah: surah,
        ayah: targetAyah,
      );
    },
  );
}

Future<void> showSajawandiPage(
  BuildContext context, {
  required int page,
  String? title,
  int? vol,
}) {
  return showDialog<void>(
    context: context,
    barrierColor: const Color(0xCC000000),
    builder: (context) {
      return BookPageViewerDialog(
        bookKey: 'sajawandi',
        initialScholar: 'السجاوندي',
        initialBookTitle: title ?? 'علل الوقوف',
        initialPageRef: '$page',
        initialPageNum: page,
        initialVol: vol,
      );
    },
  );
}

class BookPageViewerDialog extends StatefulWidget {
  const BookPageViewerDialog({
    super.key,
    required this.bookKey,
    required this.initialScholar,
    required this.initialBookTitle,
    this.initialPageRef,
    this.initialPageNum,
    this.initialVol,
    this.surah,
    this.ayah,
  });

  final String bookKey;
  final String initialScholar;
  final String initialBookTitle;
  final String? initialPageRef;
  final int? initialPageNum;
  final int? initialVol;
  final int? surah;
  final int? ayah;

  @override
  State<BookPageViewerDialog> createState() => _BookPageViewerDialogState();
}

class _BookPageViewerDialogState extends State<BookPageViewerDialog> {
  final TransformationController _transformCtrl = TransformationController();
  BookPageRecord? _record;
  bool _loading = true;
  String? _errorMessage;
  bool _showText = false;
  int _reqEpoch = 0;

  @override
  void initState() {
    super.initState();
    _loadInitial();
  }

  @override
  void dispose() {
    _transformCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadInitial() async {
    await _runLoad(() {
      if (widget.initialPageNum != null) {
        return BookPageService.fetchByPage(
          bookKey: widget.bookKey,
          pageNum: widget.initialPageNum!,
          vol: widget.initialVol,
        );
      }
      if (widget.surah != null && widget.ayah != null) {
        return BookPageService.fetchByAyah(
          bookKey: widget.bookKey,
          surah: widget.surah!,
          ayah: widget.ayah!,
        );
      }
      return Future<BookPageRecord?>.value(null);
    });
  }

  Future<void> _goToSeq(int seqIndex) async {
    await _runLoad(() => BookPageService.fetchBySeq(
          bookKey: widget.bookKey,
          seqIndex: seqIndex,
        ));
  }

  Future<void> _retry() async {
    final current = _record;
    if (current != null) {
      await _goToSeq(current.seqIndex);
    } else {
      await _loadInitial();
    }
  }

  Future<void> _runLoad(Future<BookPageRecord?> Function() loader) async {
    final epoch = ++_reqEpoch;
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final result = await loader();
      if (!mounted || epoch != _reqEpoch) return;
      _transformCtrl.value = Matrix4.identity();
      setState(() {
        _record = result;
        _loading = false;
        if (result != null && !result.hasPageText) {
          _showText = false;
        }
        if (result == null) {
          _errorMessage = 'لم يُعثر على الصفحة المطلوبة في هذا الكتاب.';
        }
      });
    } catch (e) {
      if (!mounted || epoch != _reqEpoch) return;
      setState(() {
        _loading = false;
        _errorMessage = e.toString();
      });
    }
  }

  void _copyPageText(BookPageRecord rec) {
    final txt = rec.pageText?.trim() ?? '';
    if (txt.isEmpty) return;
    Clipboard.setData(ClipboardData(text: txt));
    ScaffoldMessenger.maybeOf(context)?.showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 2),
        content: Text(
          'تم نسخ نص الصفحة ${arabicDigits(rec.pageNum)}',
          style: AppText.ui(size: 13, color: AppColors.white),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final meta = kBookDisplayMeta[widget.bookKey];
    final rec = _record;
    final titleText = rec?.titleAr.isNotEmpty == true
        ? rec!.titleAr
        : widget.initialBookTitle;
    final scholarName = rec?.scholarAr.isNotEmpty == true
        ? rec!.scholarAr
        : (meta?.scholarAr ?? widget.initialScholar);
    final edition = rec?.editionAr.isNotEmpty == true
        ? rec!.editionAr
        : (meta?.editionAr ?? '');

    final isMultiVol =
        widget.bookKey == 'sajawandi' || widget.bookKey == 'anbari';
    final pageBadgeText = rec == null
        ? ''
        : (isMultiVol
            ? 'ج${arabicDigits(rec.vol)} · صفحة ${arabicDigits(rec.pageNum)} / ${arabicDigits(rec.totalPages)}'
            : 'صفحة ${arabicDigits(rec.pageNum)} / ${arabicDigits(rec.totalPages)}');

    final size = MediaQuery.sizeOf(context);
    return Dialog(
      backgroundColor: AppColors.sheet,
      insetPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 20),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: SizedBox(
        width: size.width,
        height: size.height * 0.90,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 10, 8, 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          titleText,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: AppText.ui(
                            size: 16,
                            weight: FontWeight.w700,
                            color: AppColors.sheetText,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          edition.isEmpty
                              ? scholarName
                              : '$scholarName · $edition',
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: AppText.ui(
                            size: 11,
                            color: AppColors.sheetMuted,
                            height: 1.35,
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (rec != null && rec.hasPageText) ...[
                    if (_showText)
                      IconButton(
                        tooltip: 'نسخ نص الصفحة',
                        onPressed: () => _copyPageText(rec),
                        icon: const Icon(
                          Icons.copy_rounded,
                          size: 19,
                          color: AppColors.sheetMuted,
                        ),
                      ),
                    Padding(
                      padding: const EdgeInsets.only(top: 4, left: 4),
                      child: OutlinedButton.icon(
                        style: OutlinedButton.styleFrom(
                          foregroundColor: AppColors.goldSoft,
                          side: const BorderSide(color: AppColors.sheetLine),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 6,
                          ),
                          visualDensity: VisualDensity.compact,
                        ),
                        onPressed: () => setState(() => _showText = !_showText),
                        icon: Icon(
                          _showText
                              ? Icons.image_outlined
                              : Icons.article_outlined,
                          size: 16,
                        ),
                        label: Text(
                          _showText ? 'صورة الصفحة' : 'النص الرقمي',
                          style: AppText.ui(
                            size: 12,
                            weight: FontWeight.w600,
                            color: AppColors.goldSoft,
                          ),
                        ),
                      ),
                    ),
                  ],
                  IconButton(
                    tooltip: 'إغلاق',
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.close, color: AppColors.sheetMuted),
                  ),
                ],
              ),
            ),
            const Divider(height: 1, color: AppColors.sheetLine),
            Expanded(
              child: _buildBody(rec),
            ),
            if (rec != null) ...[
              const Divider(height: 1, color: AppColors.sheetLine),
              Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                child: Row(
                  children: [
                    TextButton.icon(
                      onPressed: (!_loading && rec.seqIndex > 1)
                          ? () => _goToSeq(rec.seqIndex - 1)
                          : null,
                      icon: const Icon(Icons.chevron_right, size: 20),
                      label: Text(
                        'السابقة',
                        style: AppText.ui(
                          size: 13,
                          weight: FontWeight.w600,
                          color: (!_loading && rec.seqIndex > 1)
                              ? AppColors.sheetText
                              : AppColors.sheetMuted.withOpacity(0.4),
                        ),
                      ),
                    ),
                    Expanded(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            pageBadgeText,
                            textAlign: TextAlign.center,
                            style: AppText.ui(
                              size: 13,
                              weight: FontWeight.w700,
                              color: AppColors.goldSoft,
                            ),
                          ),
                          if (widget.initialPageRef != null &&
                              widget.initialPageRef!.trim().isNotEmpty)
                            Text(
                              'الإحالة: ${widget.initialPageRef}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              textAlign: TextAlign.center,
                              style: AppText.ui(
                                size: 11,
                                color: AppColors.sheetMuted.withOpacity(0.85),
                              ),
                            ),
                        ],
                      ),
                    ),
                    TextButton(
                      onPressed: (!_loading && rec.seqIndex < rec.totalPages)
                          ? () => _goToSeq(rec.seqIndex + 1)
                          : null,
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            'التالية',
                            style: AppText.ui(
                              size: 13,
                              weight: FontWeight.w600,
                              color: (!_loading &&
                                      rec.seqIndex < rec.totalPages)
                                  ? AppColors.sheetText
                                  : AppColors.sheetMuted.withOpacity(0.4),
                            ),
                          ),
                          const SizedBox(width: 4),
                          const Icon(Icons.chevron_left, size: 20),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildBody(BookPageRecord? rec) {
    if (_loading && rec == null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(color: AppColors.goldSoft),
            const SizedBox(height: 14),
            Text(
              'جارٍ تحميل الصفحة...',
              style: AppText.ui(size: 13, color: AppColors.sheetMuted),
            ),
          ],
        ),
      );
    }

    if (_errorMessage != null && !_loading) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.cloud_off_outlined,
                size: 46,
                color: AppColors.goldSoft,
              ),
              const SizedBox(height: 14),
              Text(
                _errorMessage!,
                textAlign: TextAlign.center,
                style: AppText.ui(
                  size: 14,
                  color: AppColors.sheetText,
                  height: 1.6,
                ),
              ),
              const SizedBox(height: 16),
              Wrap(
                spacing: 10,
                runSpacing: 8,
                alignment: WrapAlignment.center,
                children: [
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.forest,
                      foregroundColor: AppColors.white,
                    ),
                    onPressed: _retry,
                    icon: const Icon(Icons.refresh, size: 18),
                    label: Text(
                      'إعادة المحاولة',
                      style: AppText.ui(
                        size: 13,
                        weight: FontWeight.w600,
                        color: AppColors.white,
                      ),
                    ),
                  ),
                  if (rec != null)
                    OutlinedButton(
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppColors.sheetMuted,
                        side: const BorderSide(color: AppColors.sheetLine),
                      ),
                      onPressed: () => setState(() => _errorMessage = null),
                      child: Text(
                        'العودة للصفحة الحالية',
                        style: AppText.ui(
                          size: 13,
                          color: AppColors.sheetMuted,
                        ),
                      ),
                    ),
                ],
              ),
            ],
          ),
        ),
      );
    }

    if (rec == null) {
      return const SizedBox.shrink();
    }

    if (_showText && rec.hasPageText) {
      return Stack(
        children: [
          SelectionArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(18, 16, 18, 24),
              child: Text(
                rec.pageText!,
                textDirection: TextDirection.rtl,
                textAlign: TextAlign.start,
                style: AppText.ui(
                  size: 16,
                  color: AppColors.sheetText,
                  height: 1.85,
                ),
              ),
            ),
          ),
          if (_loading)
            const Positioned.fill(
              child: ColoredBox(
                color: Color(0x55000000),
                child: Center(
                  child: CircularProgressIndicator(color: AppColors.goldSoft),
                ),
              ),
            ),
        ],
      );
    }

    return Stack(
      children: [
        InteractiveViewer(
          transformationController: _transformCtrl,
          minScale: 0.7,
          maxScale: 5.0,
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(8),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: ColoredBox(
                  color: Colors.white,
                  child: Image.memory(
                    rec.imageBytes,
                    fit: BoxFit.contain,
                    gaplessPlayback: true,
                    errorBuilder: (context, error, stackTrace) {
                      return Container(
                        padding: const EdgeInsets.all(24),
                        color: AppColors.sheetRaised,
                        child: Text(
                          'تعذّر فكّ ترميز صورة الصفحة ${arabicDigits(rec.pageNum)}.',
                          style: AppText.ui(
                            size: 13,
                            color: AppColors.sheetMuted,
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ),
            ),
          ),
        ),
        if (_loading)
          const Positioned.fill(
            child: ColoredBox(
              color: Color(0x55000000),
              child: Center(
                child: CircularProgressIndicator(color: AppColors.goldSoft),
              ),
            ),
          ),
      ],
    );
  }
}
