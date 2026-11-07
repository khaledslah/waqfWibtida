import 'package:flutter/material.dart';

import '../models/waqf_models.dart';
import '../theme/app_theme.dart';

/// Local static server for Sajawandi full-page PNGs (run via tools/serve_sajawandi_pages.py).
const sajawandiPagesBaseUrl = 'http://127.0.0.1:8765';

String sajawandiPageUrl(int page) => '$sajawandiPagesBaseUrl/page_$page.png';

/// Shows the scanned page for Al-Sajawandi (علل الوقوف), or a helpful
/// notice if another scholar's book is requested where scans are not yet available.
Future<void> showScholarBookPage(
  BuildContext context, {
  required String scholar,
  required String book,
  required String? pageStr,
  int? sajawandiPage,
}) {
  final isSajawandi = scholar.contains('السجاوندي') || book.contains('علل الوقوف');

  if (isSajawandi) {
    final page = sajawandiPage ?? parsePageNumber(pageStr);
    if (page != null) {
      return showSajawandiPage(context, page: page);
    }
  }

  // Notice for books where scanned pages are not yet bundled
  ScaffoldMessenger.maybeOf(context)?.showSnackBar(
    SnackBar(
      behavior: SnackBarBehavior.floating,
      duration: const Duration(seconds: 3),
      content: Text(
        'الصفحات المصورة المتاحة حاليًا هي لكتاب «علل الوقوف» للسجاوندي فقط ($book: ${pageStr ?? "بدون رقم"}).',
        style: AppText.ui(size: 13, color: AppColors.white),
      ),
    ),
  );
  return Future.value();
}

Future<void> showSajawandiPage(
  BuildContext context, {
  required int page,
  String? title,
}) {
  return showDialog<void>(
    context: context,
    barrierColor: const Color(0xCC000000),
    builder: (context) {
      return Dialog(
        backgroundColor: AppColors.sheet,
        insetPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 24),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: SizedBox(
          width: MediaQuery.sizeOf(context).width,
          height: MediaQuery.sizeOf(context).height * 0.88,
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 10, 4, 8),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        title ?? 'علل الوقوف · صفحة ${arabicDigits(page)}',
                        style: AppText.ui(
                          size: 15,
                          weight: FontWeight.w700,
                          color: AppColors.sheetText,
                        ),
                      ),
                    ),
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
                child: InteractiveViewer(
                  minScale: 0.5,
                  maxScale: 5,
                  child: Center(
                    child: Image.network(
                      sajawandiPageUrl(page),
                      fit: BoxFit.contain,
                      loadingBuilder: (context, child, progress) {
                        if (progress == null) return child;
                        return const Center(
                          child: CircularProgressIndicator(
                            color: AppColors.goldSoft,
                          ),
                        );
                      },
                      errorBuilder: (context, error, stackTrace) {
                        return Padding(
                          padding: const EdgeInsets.all(24),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(
                                Icons.image_not_supported_outlined,
                                size: 48,
                                color: AppColors.goldSoft,
                              ),
                              const SizedBox(height: 16),
                              Text(
                                'صورة صفحة ${arabicDigits(page)} من «علل الوقوف»',
                                style: AppText.ui(
                                  size: 16,
                                  weight: FontWeight.w700,
                                  color: AppColors.sheetText,
                                ),
                              ),
                              const SizedBox(height: 8),
                              Text(
                                'لعرض الصور الممسوحة محليًا، شغّل خادم الصور:\npython tools/serve_sajawandi_pages.py',
                                textDirection: TextDirection.rtl,
                                textAlign: TextAlign.center,
                                style: AppText.ui(
                                  size: 13,
                                  color: AppColors.sheetMuted,
                                  height: 1.6,
                                ),
                              ),
                              const SizedBox(height: 16),
                              Text(
                                'URL: ${sajawandiPageUrl(page)}',
                                textDirection: TextDirection.ltr,
                                style: AppText.ui(
                                  size: 11,
                                  color: AppColors.sheetMuted.withOpacity(0.7),
                                ),
                              ),
                            ],
                          ),
                        );
                      },
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    },
  );
}
