import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../theme/app_theme.dart';
import 'index_screen.dart';
import 'mushaf_screen.dart';
import 'review_screen.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  final ReaderController _controller = ReaderController();
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();

  @override
  void initState() {
    super.initState();
    _controller.bootstrap(initialSurah: 1);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _openDrawer() {
    _scaffoldKey.currentState?.openDrawer();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _controller,
      builder: (context, _) {
        final dockOpen = _controller.stopDockOpen;
        return PopScope(
          // Android back / edge swipe: close dock first, don't exit the app.
          canPop: !dockOpen,
          onPopInvoked: (didPop) {
            if (!didPop && _controller.stopDockOpen) {
              _controller.closeStopDock();
            }
          },
          child: Scaffold(
            key: _scaffoldKey,
            drawer: IndexDrawer(
              controller: _controller,
              onSurahSelected: () {
                if (_scaffoldKey.currentState?.isDrawerOpen ?? false) {
                  Navigator.of(context).pop();
                }
              },
            ),
            backgroundColor: AppColors.parchment,
            body: Column(
              children: [
                SafeArea(
                  bottom: false,
                  child: _TopBar(
                    controller: _controller,
                    onOpenDrawer: _openDrawer,
                  ),
                ),
                Expanded(child: _Body(controller: _controller)),
                _BottomNav(controller: _controller),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _Body extends StatelessWidget {
  const _Body({required this.controller});

  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    switch (controller.loadState) {
      case ReaderLoadState.loading:
        return const Center(
          child: CircularProgressIndicator(color: AppColors.forest),
        );
      case ReaderLoadState.error:
        return Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  controller.loadError ?? 'تعذّر التحميل',
                  textAlign: TextAlign.center,
                  style: AppText.ui(size: 16, color: AppColors.forestDeep),
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: () => controller.bootstrap(initialSurah: 1),
                  child: const Text('إعادة المحاولة'),
                ),
              ],
            ),
          ),
        );
      case ReaderLoadState.ready:
        // tab 0 = mushaf, tab 2 = review (1 reserved / unused — فهرس is drawer).
        final stackIndex = controller.tab == 2 ? 1 : 0;
        return IndexedStack(
          index: stackIndex,
          children: [
            MushafScreen(controller: controller),
            ReviewScreen(controller: controller),
          ],
        );
    }
  }
}

class _TopBar extends StatelessWidget {
  const _TopBar({
    required this.controller,
    required this.onOpenDrawer,
  });

  final ReaderController controller;
  final VoidCallback onOpenDrawer;

  @override
  Widget build(BuildContext context) {
    // Equal Expanded sides keep the app title optically centered.
    return Material(
      color: AppColors.parchment,
      elevation: 0,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
        child: SizedBox(
          height: 48,
          child: Row(
            children: [
              Expanded(
                child: controller.tab == 0
                    ? Align(
                        alignment: AlignmentDirectional.centerStart,
                        child: _SurahChip(
                          controller: controller,
                          onTap: onOpenDrawer,
                        ),
                      )
                    : const SizedBox.shrink(),
              ),
              FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(
                  'وقف وابتداء',
                  maxLines: 1,
                  style: AppText.ui(
                    size: 20,
                    weight: FontWeight.w800,
                    color: AppColors.forestDeep,
                    height: 1.2,
                  ),
                ),
              ),
              Expanded(
                child: Align(
                  alignment: AlignmentDirectional.centerEnd,
                  child: _OverflowMenu(controller: controller),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SurahChip extends StatelessWidget {
  const _SurahChip({
    required this.controller,
    required this.onTap,
  });

  final ReaderController controller;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final name = controller.currentSurahName.isEmpty
        ? '…'
        : controller.currentSurahName;
    // Drawer opens from the start edge — chevron points toward that edge.
    final rtl = Directionality.of(context) == TextDirection.rtl;
    final sideChevron = rtl ? Icons.chevron_right : Icons.chevron_left;

    return Padding(
      padding: const EdgeInsetsDirectional.only(start: 4),
      child: Tooltip(
        message: 'عرض وقوف $name',
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(6),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  sideChevron,
                  size: 20,
                  color: AppColors.forestDeep,
                ),
                const SizedBox(width: 4),
                const Icon(
                  Icons.menu_book_outlined,
                  size: 18,
                  color: AppColors.forestDeep,
                ),
                const SizedBox(width: 6),
                Flexible(
                  child: Text(
                    name,
                    maxLines: 1,
                    softWrap: false,
                    overflow: TextOverflow.ellipsis,
                    style: AppText.ui(
                      size: 14,
                      weight: FontWeight.w700,
                      color: AppColors.forestDeep,
                      height: 1.1,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _OverflowMenu extends StatelessWidget {
  const _OverflowMenu({required this.controller});

  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    return PopupMenuButton<String>(
      tooltip: 'المزيد',
      icon: const Icon(Icons.more_vert, color: AppColors.forestDeep),
      onSelected: (value) {
        if (value == 'size') {
          _showSizeDialog(context);
        } else if (value == 'legend') {
          _showLegend(context);
        }
      },
      itemBuilder: (context) => [
        PopupMenuItem(
          value: 'size',
          child: Text('حجم الخط', style: AppText.ui(size: 15)),
        ),
        PopupMenuItem(
          value: 'legend',
          child: Text('رموز الوقف', style: AppText.ui(size: 15)),
        ),
      ],
    );
  }

  void _showSizeDialog(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('حجم خط المصحف'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final option in const <(double, String)>[
                (22, 'صغير'),
                (26, 'متوسط'),
                (32, 'كبير'),
              ])
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(option.$2, style: AppText.ui(size: 16)),
                  trailing: controller.quranSize == option.$1
                      ? const Icon(Icons.check, color: AppColors.forest)
                      : null,
                  onTap: () {
                    controller.setQuranSize(option.$1);
                    Navigator.of(dialogContext).pop();
                  },
                ),
            ],
          ),
        );
      },
    );
  }

  void _showLegend(BuildContext context) {
    const rows = <(String, String)>[
      ('ط', 'تام — يحسن الوقف والابتداء بما بعده'),
      ('ج', 'جائز — يجوز الوقف والوصل'),
      ('لا', 'لا تقف — الوصل لازم'),
      ('ز', 'مجوّز — الوقف ممكن والوصل أرجح'),
      ('ص', 'صالح / مرخّص — يجوز الوقف لضرورة، والوصل أولى'),
      ('؟', 'غير محسوم — لا حكم في هذه العيّنة'),
    ];
    showDialog<void>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('رموز الوقف'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (final row in rows)
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SizedBox(
                        width: 36,
                        child: Text(
                          row.$1,
                          textAlign: TextAlign.center,
                          style: AppText.ui(
                            size: 18,
                            weight: FontWeight.w800,
                            color: AppColors.forest,
                            height: 1.2,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          row.$2,
                          style: AppText.ui(size: 14),
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: Text(
                'إغلاق',
                style: AppText.ui(
                  color: AppColors.forest,
                  weight: FontWeight.w700,
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _BottomNav extends StatelessWidget {
  const _BottomNav({required this.controller});

  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    final dark = controller.stopDockOpen && controller.panelDark;
    final bg = dark ? AppColors.sheet : AppColors.parchment;
    final line = dark ? AppColors.sheetLine : AppColors.hairline;
    final selected = dark ? AppColors.goldSoft : AppColors.forest;
    final muted = dark ? AppColors.sheetMuted : AppColors.navMuted;
    final indicator =
        dark ? AppColors.sheetRaised : AppColors.chipFill;
    // Only مصحف (0) and مراجعة (2) — map to nav indices 0 and 1.
    final navIndex = controller.tab == 2 ? 1 : 0;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: bg,
        border: Border(top: BorderSide(color: line)),
      ),
      child: SafeArea(
        top: false,
        child: NavigationBarTheme(
          data: NavigationBarThemeData(
            backgroundColor: bg,
            surfaceTintColor: Colors.transparent,
            indicatorColor: indicator,
            height: 68,
            labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
            iconTheme: WidgetStateProperty.resolveWith((states) {
              final on = states.contains(WidgetState.selected);
              return IconThemeData(
                color: on ? selected : muted,
                size: 24,
              );
            }),
            labelTextStyle: WidgetStateProperty.resolveWith((states) {
              final on = states.contains(WidgetState.selected);
              return AppText.ui(
                size: 12,
                weight: on ? FontWeight.w700 : FontWeight.w500,
                color: on ? selected : muted,
                height: 1.2,
              );
            }),
          ),
          child: NavigationBar(
            backgroundColor: bg,
            surfaceTintColor: Colors.transparent,
            indicatorColor: indicator,
            selectedIndex: navIndex,
            onDestinationSelected: (index) {
              controller.setTab(index == 0 ? 0 : 2);
            },
            destinations: const [
              NavigationDestination(
                icon: Icon(Icons.menu_book_outlined),
                selectedIcon: Icon(Icons.menu_book),
                label: 'مصحف',
              ),
              NavigationDestination(
                icon: Icon(Icons.check_circle_outline),
                selectedIcon: Icon(Icons.check_circle),
                label: 'مراجعة',
              ),
            ],
          ),
        ),
      ),
    );
  }
}
