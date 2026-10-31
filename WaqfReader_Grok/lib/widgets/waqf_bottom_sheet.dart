import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';
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

  void _approve(String id) {
    final messenger = ScaffoldMessenger.of(context);
    Navigator.of(context).pop();
    widget.controller.markForReview(id);
    messenger.showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        margin: const EdgeInsets.fromLTRB(16, 0, 16, 96),
        content: Text(
          'أُضيف الوقف إلى المراجعة',
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
              final verified = widget.controller.isVerified(stop.id);
              return Column(
                children: [
                  const _DragHandle(),
                  Expanded(
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.fromLTRB(20, 4, 20, 8),
                      child: _SheetBody(
                        stop: stop,
                        aiOpen: _aiOpen,
                        onToggleAi: () => setState(() => _aiOpen = !_aiOpen),
                        isVerseEnd: widget.controller.isVerseEnd(stop),
                        favorite: fav,
                        verified: verified,
                        onToggleFavorite: () =>
                            widget.controller.toggleFavorite(stop.id),
                        onToggleVerified: () =>
                            widget.controller.toggleVerified(stop.id),
                        onOpenPage: _openPage,
                      ),
                    ),
                  ),
                  Padding(
                    padding: EdgeInsets.fromLTRB(20, 4, 20, 12 + bottom),
                    child: _ApproveButton(
                      sent: sent,
                      onPressed: sent ? null : () => _approve(stop.id),
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
    required this.aiOpen,
    required this.onToggleAi,
    required this.isVerseEnd,
    required this.favorite,
    required this.verified,
    required this.onToggleFavorite,
    required this.onToggleVerified,
    required this.onOpenPage,
  });

  final WaqfStop stop;
  final bool aiOpen;
  final VoidCallback onToggleAi;
  final bool isVerseEnd;
  final bool favorite;
  final bool verified;
  final VoidCallback onToggleFavorite;
  final VoidCallback onToggleVerified;
  final Future<void> Function(int? page) onOpenPage;

  @override
  Widget build(BuildContext context) {
    final matn = stop.matnOpinions;
    final margin = stop.marginOpinions;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            StopBadge(
              symbol: stop.symbol,
              semanticsLabel: '${stop.label} ${stop.word}',
              core: 36,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                stop.label,
                style: AppText.ui(
                  size: 18,
                  weight: FontWeight.w700,
                  color: const Color(0xFFE7F6EE),
                ),
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
              tooltip: verified ? 'إلغاء التحقق' : 'تحقّق',
              onPressed: onToggleVerified,
              icon: Icon(
                verified ? Icons.verified : Icons.verified_outlined,
                color: verified ? AppColors.goldSoft : AppColors.sheetMuted,
              ),
            ),
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
          ],
        ),
        const SizedBox(height: 12),
        Text(
          stop.reason,
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
          title: 'رأي السجاوندي (المتن)',
        ),
        const SizedBox(height: 8),
        _OpinionTable(
          opinions: matn,
          emptyText: 'لا حكم متن مسجّل.',
          sajawandiPage: stop.textPage,
          onOpenPage: onOpenPage,
        ),
        if (margin.isNotEmpty) ...[
          const SizedBox(height: 16),
          const _SectionTitle(
            icon: Icons.notes_outlined,
            title: 'آراء من الحواشي',
          ),
          const SizedBox(height: 4),
          Text(
            'مستخرجة من هوامش علل الوقوف المرتبطة برقم الحاشية، وليست من سطر المتن.',
            style: AppText.ui(size: 12, color: AppColors.sheetMuted, height: 1.45),
          ),
          const SizedBox(height: 8),
          _OpinionTable(
            opinions: margin,
            emptyText: 'لا آراء حاشية.',
            sajawandiPage: stop.textPage,
            onOpenPage: onOpenPage,
          ),
        ],
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
        Text(
          title,
          style: AppText.ui(
            size: 15,
            weight: FontWeight.w700,
            color: AppColors.sheetText,
          ),
        ),
      ],
    );
  }
}

class _OpinionTable extends StatelessWidget {
  const _OpinionTable({
    required this.opinions,
    required this.emptyText,
    required this.sajawandiPage,
    required this.onOpenPage,
  });

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
    required this.opinion,
    required this.sajawandiPage,
    required this.onOpenPage,
  });

  final ScholarOpinion opinion;
  final int? sajawandiPage;
  final Future<void> Function(int? page) onOpenPage;

  @override
  Widget build(BuildContext context) {
    final verdict = opinion.verdict;
    return Row(
      children: [
        Expanded(
          flex: 3,
          child: Text(
            opinion.scholar,
            textAlign: TextAlign.start,
            style: AppText.ui(
              size: 14,
              weight: FontWeight.w600,
              color: AppColors.sheetText,
            ),
          ),
        ),
        Expanded(
          flex: 4,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Text(
                verdict ?? '—',
                textAlign: TextAlign.center,
                style: AppText.ui(
                  size: 14,
                  color: verdict == null
                      ? AppColors.sheetMuted
                      : AppColors.sheetText,
                ),
              ),
              if (opinion.comment != null &&
                  opinion.comment!.trim().isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(
                  opinion.comment!,
                  textAlign: TextAlign.center,
                  style: AppText.ui(
                    size: 11,
                    color: AppColors.sheetMuted,
                    height: 1.35,
                  ),
                ),
              ],
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
    final openPage = sajawandiPage ??
        (opinion.fromMargin ? null : parsePageNumber(opinion.page));

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

    // Previous reference look: page digits + book icon; book title above.
    final refRow = Row(
      mainAxisSize: MainAxisSize.min,
      textDirection: TextDirection.ltr,
      children: [
        Text(
          pageStr,
          style: AppText.ui(size: 14, color: AppColors.sheetText),
        ),
        const SizedBox(width: 4),
        const Icon(
          Icons.menu_book_outlined,
          size: 16,
          color: AppColors.sheetMuted,
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
          style: AppText.ui(size: 11, color: AppColors.sheetMuted),
        ),
        const SizedBox(height: 2),
        refRow,
      ],
    );

    if (openPage == null) {
      return Semantics(label: '${opinion.book}، صفحة $pageStr', child: body);
    }

    return Semantics(
      button: true,
      label: 'فتح صورة صفحة علل الوقوف $openPage (${opinion.book} $pageStr)',
      child: InkWell(
        onTap: () => onOpenPage(openPage),
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

class _ApproveButton extends StatelessWidget {
  const _ApproveButton({required this.sent, required this.onPressed});

  final bool sent;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: FilledButton(
        onPressed: onPressed,
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.approve,
          disabledBackgroundColor: AppColors.approve.withOpacity(0.45),
          foregroundColor: AppColors.white,
          disabledForegroundColor: AppColors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              sent ? 'في قائمة المراجعة' : 'موافق للمراجعة',
              style: AppText.ui(
                size: 16,
                weight: FontWeight.w700,
                color: AppColors.white,
              ),
            ),
            const SizedBox(width: 8),
            const Icon(Icons.check, size: 20),
          ],
        ),
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
