import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';
import '../utils/waqf_share.dart';
import 'page_image_viewer.dart';
import 'stop_badge.dart';

Future<void> showWaqfSheet(
  BuildContext context,
  ReaderController controller,
  String stopId,
) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    barrierColor: const Color(0x99000000),
    builder: (context) {
      return WaqfBottomSheet(controller: controller, stopId: stopId);
    },
  );
}

class WaqfBottomSheet extends StatefulWidget {
  const WaqfBottomSheet({
    super.key,
    required this.controller,
    required this.stopId,
  });

  final ReaderController controller;
  final String stopId;

  @override
  State<WaqfBottomSheet> createState() => _WaqfBottomSheetState();
}

class _WaqfBottomSheetState extends State<WaqfBottomSheet> {
  bool _aiOpen = false;

  void _toggleReport(String id) {
    final willAdd = !widget.controller.isSent(id);
    widget.controller.toggleSent(id);
    ScaffoldMessenger.maybeOf(context)?.showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 2),
        margin: const EdgeInsets.fromLTRB(16, 0, 16, 32),
        content: Text(
          willAdd
              ? 'أُضيف الوقف إلى قائمة المراجعة والإبلاغ'
              : 'أُزيل الوقف من قائمة المراجعة',
          style: AppText.ui(size: 14, color: AppColors.white),
        ),
      ),
    );
  }

  Future<void> _openPage(int? page) async {
    if (page == null) return;
    await showSajawandiPage(context, page: page);
  }

  @override
  Widget build(BuildContext context) {
    final height = MediaQuery.sizeOf(context).height * 0.72;
    final bottom = MediaQuery.paddingOf(context).bottom;

    return Align(
      alignment: Alignment.bottomCenter,
      child: Material(
        color: AppColors.sheet,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
        clipBehavior: Clip.antiAlias,
        child: SizedBox(
          height: height,
          child: ListenableBuilder(
            listenable: widget.controller,
            builder: (context, _) {
              final stop = widget.controller.stopById(widget.stopId);
              if (stop == null) return const _MissingStop();
              final sent = widget.controller.isSent(stop.id);
              final fav = widget.controller.isFavorite(stop.id);
              return Column(
                children: [
                  const _DragHandle(),
                  Expanded(
                    child: SelectionArea(
                      child: SingleChildScrollView(
                        padding: EdgeInsets.fromLTRB(20, 4, 20, 20 + bottom),
                        child: _SheetBody(
                          stop: stop,
                          selectedScholar: widget.controller.selectedScholar,
                          aiOpen: _aiOpen,
                          onToggleAi: () => setState(() => _aiOpen = !_aiOpen),
                          isVerseEnd: widget.controller.isVerseEnd(stop),
                          favorite: fav,
                          sent: sent,
                          onToggleFavorite: () =>
                              widget.controller.toggleFavorite(stop.id),
                          onToggleReport: () => _toggleReport(stop.id),
                          onOpenPage: _openPage,
                        ),
                      ),
                    ),
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}

class _StopShareMenu extends StatelessWidget {
  const _StopShareMenu({required this.stop});

  final WaqfStop stop;

  @override
  Widget build(BuildContext context) {
    return PopupMenuButton<String>(
      tooltip: 'خيارات الوقف (نسخ ومشاركة)',
      icon: const Icon(Icons.share_outlined, color: AppColors.sheetMuted),
      color: AppColors.sheetRaised,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: AppColors.sheetLine),
      ),
      onSelected: (action) {
        final text = formatStopText(stop);
        if (action == 'copy') {
          copyText(context, text, message: 'تم نسخ نص الوقف وأقوال العلماء');
        } else if (action == 'share') {
          shareText(context, text, subject: 'وقف: ${stop.word}');
        }
      },
      itemBuilder: (context) => [
        PopupMenuItem(
          value: 'copy',
          child: Row(
            children: [
              const Icon(Icons.copy_rounded, size: 18, color: AppColors.sheetText),
              const SizedBox(width: 8),
              Text(
                'نسخ الوقف كاملاً',
                style: AppText.ui(size: 13, color: AppColors.sheetText),
              ),
            ],
          ),
        ),
        PopupMenuItem(
          value: 'share',
          child: Row(
            children: [
              const Icon(Icons.share_outlined, size: 18, color: AppColors.sheetText),
              const SizedBox(width: 8),
              Text(
                'مشاركة الوقف',
                style: AppText.ui(size: 13, color: AppColors.sheetText),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _DragHandle extends StatelessWidget {
  const _DragHandle();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Container(
        width: 40,
        height: 4,
        margin: const EdgeInsets.only(top: 10, bottom: 12),
        decoration: BoxDecoration(
          color: AppColors.white.withOpacity(0.45),
          borderRadius: BorderRadius.circular(4),
        ),
      ),
    );
  }
}

class _SheetBody extends StatelessWidget {
  const _SheetBody({
    required this.stop,
    required this.selectedScholar,
    required this.aiOpen,
    required this.onToggleAi,
    required this.isVerseEnd,
    required this.favorite,
    required this.sent,
    required this.onToggleFavorite,
    required this.onToggleReport,
    required this.onOpenPage,
  });

  final WaqfStop stop;
  final String? selectedScholar;
  final bool aiOpen;
  final VoidCallback onToggleAi;
  final bool isVerseEnd;
  final bool favorite;
  final bool sent;
  final VoidCallback onToggleFavorite;
  final VoidCallback onToggleReport;
  final Future<void> Function(int? page) onOpenPage;

  @override
  Widget build(BuildContext context) {
    final activeOp = stop.opinionForScholar(selectedScholar);
    final activeSymbol = stop.symbolForScholar(selectedScholar);
    final activeVerdictLabel = stop.verdictLabelForScholar(selectedScholar);
    final activeIsQila = stop.isQilaForScholar(selectedScholar);
    final activeLabel = stop.labelForScholar(selectedScholar);
    final activeReason = stop.reasonForScholar(selectedScholar);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            StopBadge(
              symbol: activeSymbol,
              verdictLabel: activeVerdictLabel,
              isQila: activeIsQila,
              semanticsLabel: '$activeLabel ${stop.word}',
              core: 36,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    activeLabel,
                    style: AppText.ui(
                      size: 18,
                      weight: FontWeight.w700,
                      color: const Color(0xFFE7F6EE),
                    ),
                  ),
                  if (activeOp != null)
                    Text(
                      '${activeOp.scholar} (${activeOp.book})',
                      style: AppText.ui(
                        size: 12,
                        color: AppColors.sheetMuted,
                      ),
                    ),
                ],
              ),
            ),
            IconButton(
              tooltip: favorite ? 'إزالة من المفضلة' : 'إضافة للمفضلة',
              onPressed: onToggleFavorite,
              icon: Icon(
                favorite ? Icons.favorite : Icons.favorite_border,
                color: favorite ? const Color(0xFFE8A0A0) : AppColors.sheetMuted,
              ),
            ),
            IconButton(
              tooltip: sent ? 'في قائمة المراجعة (انقر للإلغاء)' : 'إبلاغ / إضافة للمراجعة',
              onPressed: onToggleReport,
              icon: Icon(
                sent ? Icons.flag_rounded : Icons.outlined_flag_rounded,
                color: sent ? const Color(0xFFE2A44B) : AppColors.sheetMuted,
              ),
            ),
            _StopShareMenu(stop: stop),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          stop.word,
          textAlign: TextAlign.start,
          style: AppText.quran(
            size: 40,
            weight: FontWeight.w700,
            color: AppColors.white,
            height: 1.3,
          ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            if (isVerseEnd) const _SheetTag(text: 'رأس آية'),
            if (stop.inUthmaniMushaf)
              const _SheetTag(text: 'في المصحف العثماني'),
            if (activeOp != null && activeOp.verdicts.length > 1)
              _SheetTag(text: '${arabicDigits(activeOp.verdicts.length)} أوجه للعالم'),
          ],
        ),
        const SizedBox(height: 12),
        Text(
          activeReason,
          textAlign: TextAlign.start,
          style: AppText.ui(
            size: 15,
            weight: FontWeight.w500,
            color: AppColors.sheetText,
            height: 1.75,
          ),
        ),
        const SizedBox(height: 20),
        const _SectionTitle(
          icon: Icons.menu_book_outlined,
          title: 'أقوال أئمة الوقف والابتداء',
        ),
        const SizedBox(height: 8),
        _OpinionTable(
          stop: stop,
          opinions: stop.opinions,
          emptyText: 'لا حكم مسجّل.',
          sajawandiPage: stop.textPage,
          onOpenPage: onOpenPage,
        ),
        const SizedBox(height: 12),
        _AiPanel(
          open: aiOpen,
          suggestion: stop.aiSuggestion,
          onToggle: onToggleAi,
        ),
      ],
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.icon, required this.title});

  final IconData icon;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 18, color: AppColors.goldSoft),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            title,
            style: AppText.ui(
              size: 15,
              weight: FontWeight.w700,
              color: AppColors.sheetText,
            ),
          ),
        ),
      ],
    );
  }
}

class _OpinionTable extends StatelessWidget {
  const _OpinionTable({
    required this.stop,
    required this.opinions,
    required this.emptyText,
    required this.sajawandiPage,
    required this.onOpenPage,
  });

  final WaqfStop stop;
  final List<ScholarOpinion> opinions;
  final String emptyText;
  final int? sajawandiPage;
  final Future<void> Function(int? page) onOpenPage;

  @override
  Widget build(BuildContext context) {
    if (opinions.isEmpty) {
      return Text(
        emptyText,
        style: AppText.ui(size: 14, color: AppColors.sheetMuted),
      );
    }

    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.sheetRaised,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.sheetLine),
      ),
      child: Column(
        children: [
          for (var i = 0; i < opinions.length; i++) ...[
            if (i > 0)
              const Divider(height: 1, thickness: 1, color: AppColors.sheetLine),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              child: _OpinionRow(
                stop: stop,
                opinion: opinions[i],
                sajawandiPage: sajawandiPage,
                onOpenPage: onOpenPage,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _OpinionRow extends StatelessWidget {
  const _OpinionRow({
    required this.stop,
    required this.opinion,
    required this.sajawandiPage,
    required this.onOpenPage,
  });

  final WaqfStop stop;
  final ScholarOpinion opinion;
  final int? sajawandiPage;
  final Future<void> Function(int? page) onOpenPage;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Expanded(
              flex: 3,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    opinion.scholar,
                    textAlign: TextAlign.start,
                    style: AppText.ui(
                      size: 14,
                      weight: FontWeight.w700,
                      color: AppColors.sheetText,
                    ),
                  ),
                  if (opinion.targetWord.trim().isNotEmpty)
                    Text(
                      '«${opinion.targetWord}»',
                      textAlign: TextAlign.start,
                      style: AppText.ui(
                        size: 11,
                        color: AppColors.sheetMuted,
                      ),
                    ),
                ],
              ),
            ),
            Expanded(
              flex: 5,
              child: Wrap(
                spacing: 6,
                runSpacing: 6,
                alignment: WrapAlignment.center,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  for (var i = 0; i < opinion.verdicts.length; i++)
                    _VerdictFacePill(
                      verdict: opinion.verdicts[i],
                      verdictLabel: i < opinion.verdictLabels.length
                          ? opinion.verdictLabels[i]
                          : opinion.primaryVerdictLabel,
                      symbol: i < opinion.symbols.length
                          ? opinion.symbols[i]
                          : opinion.primarySymbol,
                      isQila: i < opinion.isQila.length
                          ? opinion.isQila[i]
                          : false,
                    ),
                ],
              ),
            ),
            Expanded(
              flex: 3,
              child: Align(
                alignment: AlignmentDirectional.centerEnd,
                child: _PageRef(
                  opinion: opinion,
                  sajawandiPage: sajawandiPage,
                  onOpenPage: onOpenPage,
                ),
              ),
            ),
          ],
        ),
        if (opinion.comment != null && opinion.comment!.trim().isNotEmpty) ...[
          const SizedBox(height: 8),
          Text(
            opinion.comment!,
            textAlign: TextAlign.start,
            style: AppText.ui(
              size: 13,
              color: AppColors.sheetText.withOpacity(0.9),
              height: 1.55,
            ),
          ),
        ],
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              InkWell(
                onTap: () {
                  final text = formatOpinionText(stop, opinion);
                  copyText(
                    context,
                    text,
                    message: 'تم نسخ قول ${opinion.scholar}',
                  );
                },
                borderRadius: BorderRadius.circular(6),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.copy_rounded,
                        size: 14,
                        color: AppColors.sheetMuted,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        'نسخ',
                        style: AppText.ui(
                          size: 11,
                          color: AppColors.sheetMuted,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 8),
              InkWell(
                onTap: () {
                  final text = formatOpinionText(stop, opinion);
                  shareText(
                    context,
                    text,
                    subject: 'وقف ${stop.word} عند ${opinion.scholar}',
                  );
                },
                borderRadius: BorderRadius.circular(6),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.share_outlined,
                        size: 14,
                        color: AppColors.sheetMuted,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        'مشاركة',
                        style: AppText.ui(
                          size: 11,
                          color: AppColors.sheetMuted,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _VerdictFacePill extends StatelessWidget {
  const _VerdictFacePill({
    required this.verdict,
    required this.verdictLabel,
    required this.symbol,
    required this.isQila,
  });

  final String verdict;
  final String verdictLabel;
  final StopSymbol symbol;
  final bool isQila;

  @override
  Widget build(BuildContext context) {
    final displayVerdict =
        (isQila && !verdict.contains('قيل')) ? 'قيل: $verdict' : verdict;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.sheet,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isQila
              ? AppColors.goldSoft.withOpacity(0.75)
              : AppColors.sheetLine,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          IgnorePointer(
            child: StopBadge(
              symbol: symbol,
              verdictLabel: verdictLabel,
              isQila: isQila,
              semanticsLabel: displayVerdict,
              core: 20,
            ),
          ),
          const SizedBox(width: 4),
          Flexible(
            child: Text(
              displayVerdict,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppText.ui(
                size: 12,
                weight: FontWeight.w600,
                color: AppColors.sheetText,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PageRef extends StatelessWidget {
  const _PageRef({
    required this.opinion,
    required this.sajawandiPage,
    required this.onOpenPage,
  });

  final ScholarOpinion opinion;
  final int? sajawandiPage;
  final Future<void> Function(int? page) onOpenPage;

  @override
  Widget build(BuildContext context) {
    // Keep displayed book + ref as-is; PNG always opens علل الوقوف textPage.
    final pageStr = opinion.page;

    if (pageStr == null) {
      return Semantics(
        label: '${opinion.book}، بدون رقم صفحة',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              opinion.book,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppText.ui(size: 11, color: AppColors.sheetMuted),
            ),
            const SizedBox(height: 2),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
              decoration: BoxDecoration(
                color: AppColors.dash,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                '−',
                style: AppText.ui(
                  size: 14,
                  color: AppColors.sheetMuted,
                  height: 1.2,
                ),
              ),
            ),
          ],
        ),
      );
    }

    final isSajawandi = opinion.scholar.contains('السجاوندي') ||
        opinion.book.contains('علل الوقوف');

    final refRow = Row(
      mainAxisSize: MainAxisSize.min,
      textDirection: TextDirection.ltr,
      children: [
        Flexible(
          child: Text(
            pageStr,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppText.ui(
              size: 14,
              weight: isSajawandi ? FontWeight.w700 : FontWeight.w500,
              color: isSajawandi ? AppColors.goldSoft : AppColors.sheetText,
            ),
          ),
        ),
        const SizedBox(width: 4),
        Icon(
          Icons.menu_book_outlined,
          size: 16,
          color: isSajawandi ? AppColors.goldSoft : AppColors.sheetMuted,
        ),
      ],
    );

    final body = Column(
      crossAxisAlignment: CrossAxisAlignment.end,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          opinion.book,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          textAlign: TextAlign.end,
          style: AppText.ui(
            size: 11,
            color: isSajawandi
                ? AppColors.goldSoft.withOpacity(0.85)
                : AppColors.sheetMuted,
          ),
        ),
        const SizedBox(height: 2),
        refRow,
      ],
    );

    return Semantics(
      button: true,
      label: 'عرض صفحة ${opinion.book} $pageStr',
      child: InkWell(
        onTap: () {
          showScholarBookPage(
            context,
            scholar: opinion.scholar,
            book: opinion.book,
            pageStr: opinion.page,
            sajawandiPage: sajawandiPage,
          );
        },
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 2),
          child: body,
        ),
      ),
    );
  }
}

class _AiPanel extends StatelessWidget {
  const _AiPanel({
    required this.open,
    required this.suggestion,
    required this.onToggle,
  });

  final bool open;
  final String? suggestion;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.sheetLine),
      ),
      child: Column(
        children: [
          InkWell(
            onTap: onToggle,
            borderRadius: BorderRadius.circular(12),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              child: Row(
                children: [
                  const Icon(
                    Icons.auto_awesome,
                    size: 18,
                    color: AppColors.goldSoft,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'مقترحات AI',
                      textAlign: TextAlign.start,
                      style: AppText.ui(
                        size: 15,
                        weight: FontWeight.w600,
                        color: AppColors.sheetText,
                      ),
                    ),
                  ),
                  Icon(
                    open ? Icons.expand_less : Icons.expand_more,
                    color: AppColors.sheetMuted,
                  ),
                ],
              ),
            ),
          ),
          if (open)
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 14),
              child: Text(
                (suggestion == null || suggestion!.trim().isEmpty)
                    ? 'لا مقترح آليًا لهذه العلامة.'
                    : suggestion!,
                textAlign: TextAlign.start,
                style: AppText.ui(
                  size: 14,
                  color: AppColors.sheetText,
                  height: 1.7,
                ),
              ),
            ),
        ],
      ),
    );
  }
}


class _SheetTag extends StatelessWidget {
  const _SheetTag({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.sheetRaised,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppColors.goldSoft.withOpacity(0.55)),
      ),
      child: Text(
        text,
        style: AppText.ui(
          size: 11,
          weight: FontWeight.w700,
          color: AppColors.goldSoft,
          height: 1.1,
        ),
      ),
    );
  }
}

class _MissingStop extends StatelessWidget {
  const _MissingStop();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            'تعذر فتح هذا الوقف.',
            textAlign: TextAlign.center,
            style: AppText.ui(size: 16, color: AppColors.sheetText),
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(),
            style: FilledButton.styleFrom(backgroundColor: AppColors.approve),
            child: Text(
              'إغلاق',
              style: AppText.ui(color: AppColors.white, weight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}
