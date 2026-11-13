import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';
import '../utils/waqf_share.dart';
import 'stop_badge.dart';
import 'waqf_bottom_sheet.dart';

Future<void> showAyahOptionsSheet(
  BuildContext context,
  ReaderController controller,
  Ayah ayah,
) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    isDismissible: true,
    enableDrag: true,
    backgroundColor: Colors.transparent,
    barrierColor: const Color(0x99000000),
    builder: (context) {
      return AyahOptionsSheet(controller: controller, ayah: ayah);
    },
  );
}

class AyahOptionsSheet extends StatelessWidget {
  const AyahOptionsSheet({
    super.key,
    required this.controller,
    required this.ayah,
  });

  final ReaderController controller;
  final Ayah ayah;

  @override
  Widget build(BuildContext context) {
    final height = MediaQuery.sizeOf(context).height * 0.70;
    final bottom = MediaQuery.paddingOf(context).bottom;
    final surahName = controller.currentSurahName;
    final ayahText = ayah.words.map((w) => w.text).join(' ');

    final stopIds = ayah.words
        .map((w) => w.stopId)
        .whereType<String>()
        .toSet()
        .toList();
    final stops = stopIds
        .map((id) => controller.stopById(id))
        .whereType<WaqfStop>()
        .toList();

    return PopScope(
      canPop: true,
      child: Stack(
        children: [
          Positioned.fill(
            child: GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () {
                if (Navigator.of(context).canPop()) {
                  Navigator.of(context).pop();
                }
              },
              child: const ColoredBox(color: Colors.transparent),
            ),
          ),
          Align(
            alignment: Alignment.bottomCenter,
            child: Material(
              color: AppColors.sheet,
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(28)),
              clipBehavior: Clip.antiAlias,
              child: SizedBox(
                height: height,
                child: Column(
                  children: [
                    Center(
                      child: Container(
                        width: 40,
                        height: 4,
                        margin: const EdgeInsets.only(top: 10, bottom: 12),
                        decoration: BoxDecoration(
                          color: AppColors.white.withOpacity(0.45),
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                    ),
                    Expanded(
                      child: SingleChildScrollView(
                        padding: const EdgeInsets.fromLTRB(20, 4, 20, 16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Flexible(
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 10,
                                      vertical: 4,
                                    ),
                                    decoration: BoxDecoration(
                                      color: AppColors.sheetRaised,
                                      borderRadius: BorderRadius.circular(12),
                                      border: Border.all(
                                        color: AppColors.goldSoft,
                                      ),
                                    ),
                                    child: Text(
                                      '$surahName · الآية ${arabicDigits(ayah.number)}',
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: AppText.ui(
                                        size: 13,
                                        weight: FontWeight.w700,
                                        color: AppColors.goldSoft,
                                      ),
                                    ),
                                  ),
                                ),
                                IconButton(
                                  tooltip: 'إغلاق',
                                  onPressed: () =>
                                      Navigator.of(context).pop(),
                                  icon: const Icon(
                                    Icons.close,
                                    color: AppColors.sheetMuted,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 12),
                            DecoratedBox(
                              decoration: BoxDecoration(
                                color: AppColors.sheetRaised,
                                borderRadius: BorderRadius.circular(16),
                                border: Border.all(color: AppColors.sheetLine),
                              ),
                              child: Padding(
                                padding: const EdgeInsets.all(16),
                                child: SelectionArea(
                                  child: Text(
                                    '﴿$ayahText﴾',
                                    textDirection: TextDirection.rtl,
                                    textAlign: TextAlign.center,
                                    style: AppText.quran(
                                      size: 26,
                                      color: AppColors.white,
                                      height: 1.6,
                                    ),
                                  ),
                                ),
                              ),
                            ),
                            const SizedBox(height: 16),
                            Wrap(
                              spacing: 8,
                              runSpacing: 8,
                              children: [
                                _ActionButton(
                                  icon: Icons.copy_rounded,
                                  label: 'نسخ الآية',
                                  onTap: () {
                                    final text = formatAyahText(
                                      ayah,
                                      surahName: surahName,
                                    );
                                    copyText(
                                      context,
                                      text,
                                      message: 'تم نسخ نص الآية',
                                    );
                                  },
                                ),
                                _ActionButton(
                                  icon: Icons.share_outlined,
                                  label: 'مشاركة الآية',
                                  onTap: () {
                                    final text = formatAyahText(
                                      ayah,
                                      surahName: surahName,
                                    );
                                    shareText(
                                      context,
                                      text,
                                      subject:
                                          '$surahName: ${ayah.number}',
                                    );
                                  },
                                ),
                                _ActionButton(
                                  icon: Icons.library_books_outlined,
                                  label: 'نسخ مع الوقوف',
                                  onTap: () {
                                    final text = formatAyahWithStopsText(
                                      ayah,
                                      controller,
                                      surahName: surahName,
                                    );
                                    copyText(
                                      context,
                                      text,
                                      message: 'تم نسخ الآية مع الوقوف',
                                    );
                                  },
                                ),
                                _ActionButton(
                                  icon: Icons.ios_share_outlined,
                                  label: 'مشاركة مع الوقوف',
                                  onTap: () {
                                    final text = formatAyahWithStopsText(
                                      ayah,
                                      controller,
                                      surahName: surahName,
                                    );
                                    shareText(
                                      context,
                                      text,
                                      subject:
                                          '$surahName: ${ayah.number} مع الوقوف',
                                    );
                                  },
                                ),
                              ],
                            ),
                            const SizedBox(height: 20),
                            Row(
                              children: [
                                const Icon(
                                  Icons.bookmark_border_rounded,
                                  size: 18,
                                  color: AppColors.goldSoft,
                                ),
                                const SizedBox(width: 8),
                                Text(
                                  'وقوف هذه الآية (${arabicDigits(stops.length)})',
                                  style: AppText.ui(
                                    size: 15,
                                    weight: FontWeight.w700,
                                    color: AppColors.sheetText,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 10),
                            if (stops.isEmpty)
                              Padding(
                                padding:
                                    const EdgeInsets.symmetric(vertical: 16),
                                child: Text(
                                  'لا توجد علامات وقف مسجلة في هذه الآية.',
                                  textAlign: TextAlign.center,
                                  style: AppText.ui(
                                    size: 14,
                                    color: AppColors.sheetMuted,
                                  ),
                                ),
                              )
                            else
                              ...stops.map((stop) {
                                final activeScholar =
                                    controller.selectedScholar;
                                final label =
                                    stop.labelForScholar(activeScholar);
                                final sym =
                                    stop.symbolForScholar(activeScholar);
                                final vLabel = stop
                                    .verdictLabelForScholar(activeScholar);
                                final isQ =
                                    stop.isQilaForScholar(activeScholar);

                                return Container(
                                  margin: const EdgeInsets.only(bottom: 8),
                                  decoration: BoxDecoration(
                                    color: AppColors.sheetRaised,
                                    borderRadius: BorderRadius.circular(12),
                                    border: Border.all(
                                      color: AppColors.sheetLine,
                                    ),
                                  ),
                                  child: ListTile(
                                    leading: StopBadge(
                                      symbol: sym,
                                      verdictLabel: vLabel,
                                      isQila: isQ,
                                      semanticsLabel:
                                          'وقف $label عند ${stop.word}',
                                      core: 28,
                                    ),
                                    title: Text(
                                      stop.word,
                                      style: AppText.quran(
                                        size: 20,
                                        color: AppColors.white,
                                      ),
                                    ),
                                    subtitle: Text(
                                      '$label · ${arabicDigits(stop.opinions.length)} أقوال للأئمة',
                                      style: AppText.ui(
                                        size: 12,
                                        color: AppColors.sheetMuted,
                                      ),
                                    ),
                                    trailing: const Icon(
                                      Icons.arrow_back_ios_new,
                                      size: 14,
                                      color: AppColors.sheetMuted,
                                    ),
                                    onTap: () {
                                      Navigator.of(context).pop();
                                      controller.select(stop.id);
                                      showWaqfSheet(
                                        context,
                                        controller,
                                        stop.id,
                                      );
                                    },
                                  ),
                                );
                              }),
                            SizedBox(height: bottom),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  const _ActionButton({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.sheetRaised,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.sheetLine),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 16, color: AppColors.goldSoft),
              const SizedBox(width: 6),
              Text(
                label,
                style: AppText.ui(
                  size: 13,
                  weight: FontWeight.w600,
                  color: AppColors.sheetText,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
