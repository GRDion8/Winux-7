// SPDX-License-Identifier: GPL-3.0-only
// Winux 7 Control Panel: an intentionally limited front end to installed settings modules.
#include <QtWidgets>
#include <QStorageInfo>
#include <QSysInfo>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <cstdio>
#include "wallpaper.hpp"

struct Setting { QString id, category, title, detail, icon, module; };
static const QList<Setting> settings = {
    {"wallpaper", "Appearance and Looks", "Desktop Background", "Choose a wallpaper for your desktop", "preferences-desktop-wallpaper", ""},
    {"system", "System and Security", "System", "View basic information about your computer", "computer", ""},
    {"power", "System and Security", "Power Options", "Choose sleep and power-saving settings", "preferences-system-power-management", "kcm_powerdevilprofilesconfig"},
    {"network", "Network and Internet", "Network Connections", "Connect to Wi-Fi and manage your connections", "network-wireless", "kcm_networkmanagement"},
    {"sound", "Hardware and Sound", "Sound", "Adjust volume, speakers and microphones", "audio-volume-high", "kcm_pulseaudio"},
    {"display", "Hardware and Sound", "Display", "Adjust screen resolution and arrange monitors", "preferences-desktop-display", "kcm_kscreen"},
    {"mouse", "Hardware and Sound", "Mouse", "Adjust pointer speed and buttons", "input-mouse", "kcm_mouse"},
    {"keyboard", "Hardware and Sound", "Keyboard", "Choose keyboard layouts and typing options", "input-keyboard", "kcm_keyboard"},
    {"printers", "Hardware and Sound", "Devices and Printers", "Manage printers and print jobs", "printer", "kcm_printer_manager"},
    {"bluetooth", "Hardware and Sound", "Bluetooth Devices", "Connect wireless accessories", "preferences-system-bluetooth", "kcm_bluetooth"},
    {"defaults", "Programs", "Default Programs", "Choose which applications open your files", "preferences-desktop-default-applications", "kcm_componentchooser"},
    {"wine", "Programs", "Windows Application Settings", "Configure Windows application compatibility", "wine", ""},
    {"users", "User Accounts", "User Accounts", "Manage your account and password", "system-users", "kcm_users"},
    {"date", "Clock, Language, and Region", "Date and Time", "Set the clock and time zone", "preferences-system-time", "kcm_clock"},
    {"language", "Clock, Language, and Region", "Region and Language", "Choose your language and regional formats", "preferences-desktop-locale", "kcm_regionandlang"},
    {"accessibility", "Ease of Access", "Ease of Access Center", "Adjust accessibility options", "preferences-desktop-accessibility", "kcm_access"}
};
static QStringList commandFor(const Setting &s) {
    if (s.id == "system" || s.id == "wallpaper") return {};
    if (s.id == "wine") return {"/usr/bin/winecfg"};
    return {"/usr/bin/kcmshell6", s.module};
}
static QSet<QString> availableModules() {
    QProcess p;
    p.start("/usr/bin/kcmshell6", {"--list"});
    if (!p.waitForFinished(5000)) { p.kill(); p.waitForFinished(); return {}; }
    QSet<QString> result;
    const QString output = QString::fromUtf8(p.readAllStandardOutput());
    for (const QString &line : output.split('\n')) {
        const auto m = QRegularExpression("^\\s*(\\S+)\\s+-").match(line);
        if (m.hasMatch()) result.insert(m.captured(1));
    }
    return result;
}
class ControlPanel : public QMainWindow {
public:
    QLineEdit *search;
    QWidget *body;
    QVBoxLayout *items;
    QSet<QString> modules;
    QString category;
    ControlPanel(bool preview=false) {
        setWindowTitle("Control Panel — Winux 7");
        setWindowIcon(QIcon::fromTheme("preferences-system"));
        resize(960, 670); setMinimumSize(760, 520);
        modules = preview ? QSet<QString>{} : availableModules();
        if (preview) for (const auto &s : settings) modules.insert(s.module);
        auto outer = new QWidget; auto layout = new QVBoxLayout(outer); layout->setContentsMargins(0,0,0,0);
        auto toolbar = new QWidget; toolbar->setObjectName("navigation");
        auto nav = new QHBoxLayout(toolbar);
        auto home = new QPushButton("‹  Control Panel");
        home->setFlat(true); home->setCursor(Qt::PointingHandCursor);
        nav->addWidget(home); nav->addStretch();
        search = new QLineEdit; search->setPlaceholderText("Search Control Panel"); search->setClearButtonEnabled(true); search->setMaximumWidth(290);
        nav->addWidget(search); layout->addWidget(toolbar);
        auto split = new QHBoxLayout;
        auto sidebar = new QWidget; sidebar->setObjectName("sidebar"); sidebar->setFixedWidth(195);
        auto side = new QVBoxLayout(sidebar); side->setContentsMargins(18,20,12,20);
        auto homeLink = new QPushButton("Control Panel Home"); homeLink->setFlat(true); side->addWidget(homeLink);
        side->addSpacing(15);
        QStringList categories;
        for (const auto &s : settings) if (!categories.contains(s.category)) categories << s.category;
        for (const auto &c : categories) {
            auto b = new QPushButton(c); b->setFlat(true); b->setCursor(Qt::PointingHandCursor);
            b->setStyleSheet("text-align:left; padding:6px 0;");
            connect(b,&QPushButton::clicked,this,[this,c]{category=c; search->clear(); render();}); side->addWidget(b);
        }
        side->addStretch();
        auto brand = new QLabel("Winux 7"); brand->setStyleSheet("font-size:20px; color:#52677e"); side->addWidget(brand);
        split->addWidget(sidebar);
        auto scroll = new QScrollArea; scroll->setWidgetResizable(true); scroll->setFrameShape(QFrame::NoFrame);
        body = new QWidget; items = new QVBoxLayout(body); items->setContentsMargins(25,16,25,20);
        scroll->setWidget(body); split->addWidget(scroll,1); layout->addLayout(split,1);
        auto status = new QLabel("  Adjust your computer's settings"); status->setObjectName("status"); layout->addWidget(status);
        setCentralWidget(outer);
        setStyleSheet("QMainWindow,QScrollArea,QWidget {background:#ffffff; color:#202020;} #navigation {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #f8fbfe,stop:1 #dce9f5); border-bottom:1px solid #9eb5cd;} #sidebar {background:#edf3fa;} QPushButton[flat=\"true\"] {color:#1762a0; border:0; padding:7px; text-align:left;} QPushButton[flat=\"true\"]:hover {text-decoration:underline; color:#003d77;} QLineEdit {border:1px solid #90a9bc; padding:6px; background:white;} #status {background:#edf1f5; padding:5px; border-top:1px solid #b9c7d5;} QToolButton {border:1px solid transparent; padding:8px; text-align:left;} QToolButton:hover {background:#edf6ff; border:1px solid #c0d9f1;} QToolButton:disabled {color:#777;}");
        auto goHome=[this]{category.clear();search->clear();render();};
        connect(home,&QPushButton::clicked,this,goHome); connect(homeLink,&QPushButton::clicked,this,goHome);
        connect(search,&QLineEdit::textChanged,this,[this]{render();}); render();
    }
    void render() {
        while (auto item=items->takeAt(0)) { if (item->widget()) delete item->widget(); delete item; }
        auto heading=new QLabel(category.isEmpty()?"Adjust your computer's settings":category);
        heading->setStyleSheet("color:#235e2c;font-size:21px;padding-bottom:10px;"); items->addWidget(heading);
        if (category.isEmpty() && search->text().isEmpty()) {
            auto gridWidget=new QWidget; auto grid=new QGridLayout(gridWidget); grid->setContentsMargins(0,0,0,0);
            QStringList groups; for(const auto &s:settings) if(!groups.contains(s.category)) groups << s.category;
            int n=0;
            for(const auto &group:groups) {
                auto card=new QWidget; auto v=new QVBoxLayout(card); v->setContentsMargins(3,5,8,10);
                auto title=new QPushButton(group);title->setFlat(true);title->setStyleSheet("color:#235e2c;font-size:16px;text-align:left;padding:5px 0;");
                connect(title,&QPushButton::clicked,this,[this,group]{category=group;render();});v->addWidget(title);
                int links=0;
                for(const auto &s:settings) if(s.category==group && links++<3) {
                    auto b=new QPushButton(QIcon::fromTheme(s.icon),s.title);b->setFlat(true);b->setToolTip(s.detail);b->setCursor(Qt::PointingHandCursor);
                    const bool enabled=s.module.isEmpty()?s.id!="wine" || QFileInfo::exists("/usr/bin/winecfg"):modules.contains(s.module);
                    b->setEnabled(enabled);if(!enabled)b->setToolTip("This component is not installed.");
                    connect(b,&QPushButton::clicked,this,[this,s]{openSetting(s);});v->addWidget(b);
                }
                v->addStretch();grid->addWidget(card,n/2,n%2);++n;
            }
            grid->setColumnStretch(0,1);grid->setColumnStretch(1,1);items->addWidget(gridWidget);items->addStretch();return;
        }
        QString last; int found=0;
        for (const auto &s : settings) {
            if (!category.isEmpty() && s.category!=category) continue;
            if (!(s.title+" "+s.category+" "+s.detail).contains(search->text(),Qt::CaseInsensitive)) continue;
            if (last!=s.category) {
                last=s.category; auto label=new QLabel(last); label->setStyleSheet("color:#235e2c;font-size:16px;padding-top:10px;"); items->addWidget(label);
            }
            auto b=new QToolButton; b->setToolButtonStyle(Qt::ToolButtonTextBesideIcon);
            b->setIcon(QIcon::fromTheme(s.icon)); b->setIconSize(QSize(32,32));
            b->setText(s.title+"\n"+s.detail); b->setSizePolicy(QSizePolicy::Expanding,QSizePolicy::Preferred);
            bool enabled=s.module.isEmpty() || modules.contains(s.module);
            if (s.id=="wine") enabled=QFileInfo::exists("/usr/bin/winecfg");
            b->setEnabled(enabled); b->setToolTip(enabled?s.detail:"This component is not installed.");
            connect(b,&QToolButton::clicked,this,[this,s]{openSetting(s);});items->addWidget(b);++found;
        }
        if (!found) items->addWidget(new QLabel("No matching settings. Try another search."));
        items->addStretch();
    }
    void openSetting(const Setting &s) {
        if (s.id=="wallpaper") { Wallpaper::dialog(this); return; }
        if (s.id=="system") {
            QMessageBox::information(this,"System — Winux 7",QString("Winux 7\n\nComputer: %1\nProcessor architecture: %2\nSystem storage available: %3 GiB\n\nBuilt on Arch Linux, KDE Plasma and AeroThemePlasma.\nThird-party components retain their licenses and credits.")
                .arg(QSysInfo::machineHostName(),QSysInfo::currentCpuArchitecture())
                .arg(QStorageInfo::root().bytesAvailable()/double(1024*1024*1024),0,'f',1)); return;
        }
        auto args=commandFor(s); auto program=args.takeFirst();
        if (!s.module.isEmpty() && !modules.contains(s.module)) {
            QMessageBox::information(this,s.title,"This settings component is not installed.");return;
        }
        if (!QProcess::startDetached(program,args)) QMessageBox::warning(this,s.title,"The settings window could not be opened.");
    }
};
int main(int argc,char **argv) {
    QApplication app(argc,argv); app.setApplicationName("winux-control-panel"); app.setApplicationDisplayName("Control Panel");
    const auto args=app.arguments();
    if (args.contains("--wallpaper-service")) return Wallpaper::service(app);
    if (args.contains("--restore-wallpaper") || (args.size()>1 && args[1]=="--set-wallpaper")) {
        try {
            if (args.contains("--restore-wallpaper")) Wallpaper::restore();
            else { if(args.size()!=3)return 2;Wallpaper::choose(QFileInfo(args[2]).absoluteFilePath()); }
            return 0;
        } catch(const std::exception &e) { std::fprintf(stderr,"%s\n",e.what());return 1; }
    }
    if (args.contains("--list-actions")) {
        QJsonObject all; for (const auto &s:settings) all[s.id]=QJsonArray::fromStringList(commandFor(s));
        std::puts(QJsonDocument(all).toJson().constData());return 0;
    }
    if (args.size()>1 && args[1]=="--dry-run") {
        if (args.size()!=3) return 2;
        for (const auto &s:settings) if (args[2]==s.id || args[2]==s.module) {
            std::puts(QJsonDocument(QJsonArray::fromStringList(commandFor(s))).toJson().constData());return 0;
        }
        return 2;
    }
    const bool smoke=args.contains("--smoke-test");
    ControlPanel panel(smoke || args.contains("--preview")); panel.show();
    if(args.contains("--preview") && args.contains("--screenshot")) {
        int i=args.indexOf("--screenshot"); if(i+1>=args.size())return 2;
        QTimer::singleShot(150,&app,[&,i]{app.exit(panel.grab().save(args[i+1])?0:2);});
    }
    if (smoke) QTimer::singleShot(100,&app,[&]{panel.search->setText("sound"); if (panel.items->count()<3) app.exit(2); else app.exit(0);});
    // Aero invokes systemsettings with a KCM name for specific Start-menu links.
    if (args.size()>1 && !args[1].startsWith("--")) {
        for (const auto &s:settings) if (args[1]==s.id || (!s.module.isEmpty() && args[1]==s.module)) {
            QTimer::singleShot(0,&panel,[&panel,s]{panel.openSetting(s);});break;
        }
        // Unknown/appearance modules stay on the curated home screen.
    }
    return app.exec();
}
