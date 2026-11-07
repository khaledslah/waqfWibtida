import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';

/// Sidebar drawer that slides in from the edge to display the Surah index.
class IndexDrawer extends StatelessWidget {
  const IndexDrawer({
    super.key,
    required this.controller,
    this.onSurahSelected,
  });

  final ReaderController controller;
  final VoidCallback? onSurahSelected;

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final drawerWidth = width > 460 ? 380.0 : width * 0.85;

    return Drawer(
      backgroundColor: AppColors.parchment,
      surfaceTintColor: Colors.transparent,
      width: drawerWidth,
      child: SafeArea(
        child: IndexScreen(
          controller: controller,
          onSurahSelected: onSurahSelected,
          isDrawer: true,
        ),
      ),
    );
  }
}

class IndexScreen extends StatefulWidget {
  const IndexScreen({
    super.key,
    required this.controller,
    this.onSurahSelected,
    this.isDrawer = false,
  });

  final ReaderController controller;
  final VoidCallback? onSurahSelected;
  final bool isDrawer;

  @override
  State<IndexScreen> createState() => _IndexScreenState();
}

class _IndexScreenState extends State<IndexScreen> {
  final TextEditingController _searchController = TextEditingController();
  String _query = '';

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  List<SurahIndexEntry> get _filteredSurahs {
    final surahs = widget.controller.sampleSurahs;
    if (_query.isEmpty) return surahs;
    final q = _query.toLowerCase().trim();
    final cleanQ = q.replaceAll('أ', 'ا').replaceAll('إ', 'ا').replaceAll('آ', 'ا');
    return surahs.where((s) {
      final sName = s.name.replaceAll('أ', 'ا').replaceAll('إ', 'ا').replaceAll('آ', 'ا');
      final sNum = s.number.toString();
      final sNumAr = arabicDigits(s.number);
      return sName.contains(cleanQ) || sNum.contains(q) || sNumAr.contains(q);
    }).toList();
  }

  Future<void> _open(
    BuildContext context,
    ReaderController controller,
    SurahIndexEntry surah,
  ) async {
    // Close sidebar drawer immediately when surah is chosen
    if (Navigator.of(context).canPop()) {
      Navigator.of(context).pop();
    }
    widget.onSurahSelected?.call();

    if (surah.number == controller.currentSurah) {
      controller.setTab(0);
      return;
    }
    await controller.loadSurah(surah.number);
    if (!context.mounted) return;
    if (controller.loadState == ReaderLoadState.ready) {
      controller.setTab(0);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(controller.loadError ?? 'تعذّر فتح السورة')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final surahs = _filteredSurahs;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      const Icon(
                        Icons.menu_book_rounded,
                        size: 22,
                        color: AppColors.forest,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        'الفهرس',
                        style: AppText.ui(
                          size: 22,
                          weight: FontWeight.w700,
                          color: AppColors.forestDeep,
                        ),
                      ),
                    ],
                  ),
                  if (widget.isDrawer || Navigator.of(context).canPop())
                    IconButton(
                      tooltip: 'إغلاق الفهرس',
                      icon: const Icon(Icons.close, color: AppColors.muted),
                      onPressed: () {
                        if (Navigator.of(context).canPop()) {
                          Navigator.of(context).pop();
                        }
                      },
                    ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                controller.catalog.isEmpty
                    ? 'لا فهرس محمّل'
                    : '${arabicDigits(controller.catalog.length)} سورة من علل الوقوف',
                style: AppText.ui(size: 13, color: AppColors.muted),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _searchController,
                textDirection: TextDirection.rtl,
                decoration: InputDecoration(
                  hintText: 'ابحث باسم السورة أو رقمها...',
                  hintStyle: AppText.ui(size: 13, color: AppColors.muted),
                  prefixIcon: const Icon(Icons.search, size: 20, color: AppColors.muted),
                  suffixIcon: _searchController.text.isNotEmpty
                      ? IconButton(
                          icon: const Icon(Icons.clear, size: 18, color: AppColors.muted),
                          onPressed: () {
                            setState(() {
                              _searchController.clear();
                              _query = '';
                            });
                          },
                        )
                      : null,
                  filled: true,
                  fillColor: AppColors.white,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: AppColors.hairline),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: AppColors.hairline),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: AppColors.forest, width: 1.5),
                  ),
                ),
                onChanged: (val) {
                  setState(() {
                    _query = val.trim();
                  });
                },
              ),
            ],
          ),
        ),
        const Divider(height: 1, thickness: 1, color: AppColors.hairline),
        Expanded(
          child: surahs.isEmpty
              ? const _EmptyIndex()
              : ListView.builder(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
                  itemCount: surahs.length,
                  itemBuilder: (context, index) {
                    final surah = surahs[index];
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: _SurahCard(
                        surah: surah,
                        isSelected: surah.number == controller.currentSurah,
                        onTap: () => _open(context, controller, surah),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }
}

class _EmptyIndex extends StatelessWidget {
  const _EmptyIndex();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 48),
      child: Text(
        'لا سور في الفهرس مطابقة للبحث.',
        textAlign: TextAlign.center,
        style: AppText.ui(size: 16, color: AppColors.forestDeep),
      ),
    );
  }
}

class _SurahCard extends StatelessWidget {
  const _SurahCard({
    required this.surah,
    required this.onTap,
    this.isSelected = false,
  });

  final SurahIndexEntry surah;
  final VoidCallback onTap;
  final bool isSelected;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: isSelected ? AppColors.chipFill : AppColors.white,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isSelected ? AppColors.forest : AppColors.hairline,
              width: isSelected ? 1.5 : 1,
            ),
          ),
          child: Row(
            children: [
              Container(
                width: 42,
                height: 42,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: isSelected ? AppColors.white : AppColors.chipFill,
                  border: Border.all(color: AppColors.forest),
                ),
                child: Text(
                  arabicDigits(surah.number),
                  style: AppText.ui(
                    size: 14,
                    weight: FontWeight.w700,
                    color: AppColors.forest,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      surah.name,
                      style: AppText.ui(
                        size: 16,
                        weight: FontWeight.w700,
                        color: AppColors.forestDeep,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      surah.detail,
                      style: AppText.ui(size: 12, color: AppColors.muted),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              _StatusChip(status: surah.status, label: surah.statusLabel),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status, required this.label});

  final SurahLoadStatus status;
  final String label;

  @override
  Widget build(BuildContext context) {
    final Color fill;
    final Color foreground;
    switch (status) {
      case SurahLoadStatus.inProgress:
        fill = AppColors.chipFill;
        foreground = AppColors.forest;
      case SurahLoadStatus.notStarted:
        fill = const Color(0xFFEFECE4);
        foreground = AppColors.muted;
      case SurahLoadStatus.awaitingReview:
        fill = AppColors.amberWash;
        foreground = AppColors.forestDeep;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: fill,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: foreground.withOpacity(0.35)),
      ),
      child: Text(
        label,
        style: AppText.ui(
          size: 12,
          weight: FontWeight.w700,
          color: foreground,
          height: 1.2,
        ),
      ),
    );
  }
}
