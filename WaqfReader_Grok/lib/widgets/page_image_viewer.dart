import 'package:flutter/material.dart';

import '../models/waqf_models.dart';
import '../theme/app_theme.dart';

/// Local static server for Sajawandi full-page PNGs (see tools / python http.server).
const sajawandiPagesBaseUrl = 'http://127.0.0.1:8765';

String sajawandiPageUrl(int page) => '$sajawandiPagesBaseUrl/page_$page.png';

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
                  maxScale: 4,
                  child: Image.network(
                    sajawandiPageUrl(page),
                    fit: BoxFit.contain,
                    loadingBuilder: (context, child, progress) {
                      if (progress == null) return child;
                      return const Center(
                        child: CircularProgressIndicator(color: AppColors.goldSoft),
                      );
                    },
                    errorBuilder: (context, error, stack) {
                      return Padding(
                        padding: const EdgeInsets.all(24),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              'تعذّر فتح صورة الصفحة $page.\n'
                              'تأكد أن خادم الصفحات يعمل على المنفذ 8765.',
                              textAlign: TextAlign.center,
                              style: AppText.ui(
                                size: 14,
                                color: AppColors.sheetText,
                                height: 1.6,
                              ),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              sajawandiPageUrl(page),
                              textAlign: TextAlign.center,
                              style: AppText.ui(
                                size: 11,
                                color: AppColors.sheetMuted,
                              ),
                            ),
                          ],
                        ),
                      );
                    },
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
