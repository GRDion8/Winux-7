// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <QtWidgets>
#include <QtDBus>
#include <stdexcept>

namespace Wallpaper {
inline QString preferenceFile() {
    return QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation)+"/winux-7/wallpaper.json";
}
inline QString defaultImage() {
    QFile defaults("/usr/share/winux-setup/wallpaper-path");
    if (!defaults.open(QIODevice::ReadOnly)) throw std::runtime_error("The default Winux wallpaper is missing.");
    return QString::fromUtf8(defaults.readAll()).trimmed();
}
inline QString selected() {
    QFile file(preferenceFile());
    if (file.exists()) {
        if (!file.open(QIODevice::ReadOnly)) throw std::runtime_error("Cannot read the saved wallpaper choice.");
        QJsonParseError error;
        const auto value=QJsonDocument::fromJson(file.readAll(), &error).object().value("image").toString();
        if (error.error==QJsonParseError::NoError && QFileInfo(value).isFile() && QImageReader(value).canRead()) return value;
    }
    return defaultImage();
}
inline void validate(const QString &path) {
    if (!QFileInfo(path).isAbsolute() || !QFileInfo(path).isFile() || !QImageReader(path).canRead())
        throw std::runtime_error("Choose a readable picture file.");
}
inline void save(const QString &path) {
    QDir().mkpath(QFileInfo(preferenceFile()).absolutePath());
    QSaveFile file(preferenceFile());
    const auto data=QJsonDocument(QJsonObject{{"image",path}}).toJson();
    if (!file.open(QIODevice::WriteOnly) || file.write(data)!=data.size() || !file.commit())
        throw std::runtime_error("Could not save your wallpaper choice.");
}
inline QString importPicture(const QString &source) {
    validate(source);
    QFile file(source);
    if (!file.open(QIODevice::ReadOnly)) throw std::runtime_error("Cannot read the picture.");
    QCryptographicHash hash(QCryptographicHash::Sha256);
    if (!hash.addData(&file)) throw std::runtime_error("Cannot read the picture.");
    const auto folder=QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation)+"/winux-7/wallpapers";
    if (!QDir().mkpath(folder)) throw std::runtime_error("Cannot create the wallpaper folder.");
    const auto target=folder+"/"+QString::fromLatin1(hash.result().toHex())+"."+QFileInfo(source).suffix();
    if (!QFileInfo::exists(target) && !QFile::copy(source,target)) throw std::runtime_error("Cannot keep a local copy of this picture.");
    validate(target);
    return target;
}
inline void apply(const QString &image) {
    validate(image);
    QDBusInterface shell("org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell", QDBusConnection::sessionBus());
    shell.setTimeout(2000);
    if (!shell.isValid()) throw std::runtime_error("The desktop is not ready yet.");
    const QString uri=QUrl::fromLocalFile(image).toString(QUrl::FullyEncoded);
    const int count=QGuiApplication::screens().size();
    if (!count) throw std::runtime_error("No desktop screen is ready.");
    for (int screen=0; screen<count; ++screen) {
        QDBusReply<QVariantMap> before=shell.call("wallpaper",uint(screen));
        if (!before.isValid() || !before.value().contains("Image")) throw std::runtime_error("A desktop wallpaper is not ready yet.");
        if (before.value().value("wallpaperPlugin").toString()=="org.kde.image" &&
            QUrl(before.value().value("Image").toString())==QUrl(uri)) continue;
        // This narrow, synchronously saved API works with Plasma's layout lock.
        // evaluateScript is deliberately unavailable once the desktop is locked.
        auto reply=shell.call("setWallpaper",QString("org.kde.image"),QVariantMap{{"Image",uri}},uint(screen));
        if (reply.type()==QDBusMessage::ErrorMessage) throw std::runtime_error(reply.errorMessage().toStdString());
        QDBusReply<QVariantMap> after=shell.call("wallpaper",uint(screen));
        if (!after.isValid() || after.value().value("wallpaperPlugin").toString()!="org.kde.image" ||
            QUrl(after.value().value("Image").toString())!=QUrl(uri))
            throw std::runtime_error("The desktop has not confirmed the wallpaper yet.");
    }
}
inline QString changeLockPath() {
    QDir().mkpath(QFileInfo(preferenceFile()).absolutePath());
    return QFileInfo(preferenceFile()).absolutePath()+"/wallpaper-change.lock";
}
inline void choose(const QString &source) {
    const auto copy=importPicture(source);
    QLockFile lock(changeLockPath());
    if(!lock.tryLock(3000))throw std::runtime_error("The desktop is updating. Please try again.");
    apply(copy);
    save(copy);
}
inline void restore() {
    QLockFile lock(changeLockPath());
    if(!lock.tryLock(3000))throw std::runtime_error("The desktop is updating. Please try again.");
    const auto image=selected(); apply(image); save(image);
}
inline bool setupReady() {
    QString state=qEnvironmentVariable("XDG_STATE_HOME");
    if(state.isEmpty())state=QDir::homePath()+"/.local/state";
    const auto config=QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation);
    return QFileInfo::exists(state+"/winux-desktop-v1/desktop-complete") &&
        QFileInfo::exists(state+"/winux-desktop-v1/wine-complete") &&
        (!QFileInfo::exists(config+"/autostart/aerothemeplasma-first-login.desktop") ||
         QFileInfo::exists(state+"/win7-aero-postinstall/first-login-complete"));
}
inline int service(QApplication &app) {
    const auto config=QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation)+"/winux-7";
    QDir().mkpath(config);
    QLockFile lock(config+"/wallpaper-service.lock");
    if(!lock.tryLock())return 0;
    app.setQuitOnLastWindowClosed(false);
    QTimer timer;QString lastError;
    auto repair=[&]{
        if(!setupReady())return; // Do not compete with first-login layout initialization.
        QLockFile changeLock(changeLockPath());
        if(!changeLock.tryLock())return;
        try {apply(selected());lastError.clear();}
        catch(const std::exception &e){
            if(lastError!=e.what()){lastError=e.what();qWarning().noquote()<<lastError;}
        }
    };
    QObject::connect(&timer,&QTimer::timeout,&app,repair);
    timer.start(5000);QTimer::singleShot(0,&app,repair);
    // Keep repairing late shell startup, shell restarts, activity and screen changes.
    // apply() reads back each screen and writes only when the image actually differs.
    return app.exec();
}
inline void dialog(QWidget *parent) {
    QDialog dialog(parent); dialog.setWindowTitle("Desktop Background — Winux 7");dialog.resize(660,490);
    auto layout=new QVBoxLayout(&dialog);
    auto title=new QLabel("Choose your desktop background");title->setStyleSheet("font-size:21px;color:#235e2c;padding:10px;");layout->addWidget(title);
    auto preview=new QLabel;preview->setAlignment(Qt::AlignCenter);preview->setMinimumSize(420,250);layout->addWidget(preview,1);
    auto note=new QLabel("Your picture will be used on all connected screens and kept after restarting.");note->setWordWrap(true);layout->addWidget(note);
    QString image;
    auto refresh=[&] { preview->setPixmap(QPixmap(image).scaled(580,300,Qt::KeepAspectRatio,Qt::SmoothTransformation)); };
    try { image=selected();refresh(); } catch(const std::exception &e) { note->setText(e.what()); }
    auto buttons=new QDialogButtonBox(QDialogButtonBox::Save|QDialogButtonBox::Cancel);
    auto browse=buttons->addButton("Browse…",QDialogButtonBox::ActionRole);
    QObject::connect(browse,&QPushButton::clicked,&dialog,[&]{
        const auto path=QFileDialog::getOpenFileName(&dialog,"Choose a picture",QDir::homePath(),"Pictures (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*)");
        if(path.isEmpty())return;
        try {validate(path);image=path;refresh();} catch(const std::exception &e){QMessageBox::warning(&dialog,"Desktop Background",e.what());}
    });
    QObject::connect(buttons,&QDialogButtonBox::accepted,&dialog,[&]{
        try {choose(image);dialog.accept();} catch(const std::exception &e){QMessageBox::warning(&dialog,"Desktop Background",e.what());}
    });
    QObject::connect(buttons,&QDialogButtonBox::rejected,&dialog,&QDialog::reject);
    layout->addWidget(buttons);dialog.exec();
}
}
