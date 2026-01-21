;;; exactas-cal2org.el --- Description -*- lexical-binding: t; -*-
;;
;; Copyright (C) 2025 Pablo Cobelli
;;
;; Author: Pablo Cobelli <pablo.cobelli@gmail.com>
;; Maintainer: Pablo Cobelli <pablo.cobelli@gmail.com>
;; Created: March 04, 2025
;; Modified: March 04, 2025
;; Version: 0.0.1
;; Keywords: abbrev bib c calendar comm convenience data docs emulations extensions faces files frames games hardware help hypermedia i18n internal languages lisp local maint mail matching mouse multimedia news outlines processes terminals tex text tools unix vc
;; Homepage: https://github.com/pablocobelli/exactas-cal2org
;; Package-Requires: ((emacs "24.3"))
;;
;; This file is not part of GNU Emacs.
;;
;;; Commentary:
;;
;;  Description
;;
;;; Code:

(defgroup exactas-cal2org nil
  "Import Exactas academic calendar to Org."
  :group 'convenience)

(defcustom exactas-cal2org-python-executable
  (or (executable-find "python3") "python3")
  "Absolute path to Python executable used to run exactas-cal2org.py.
(Eg: /opt/homebrew/bin/python3 or /path/a/venv/bin/python)."
  :type 'string
  :group 'exactas-cal2org)

(defvar exactas-cal2org-directory
  (file-name-directory (or load-file-name buffer-file-name))
  "Directory where the exactas-cal2org package is installed.")

(defun exactas-cal2org-run ()
  "Run exactas-cal2org.py and insert its output at point."
  (interactive)
  (let* ((script (expand-file-name "exactas-cal2org.py" exactas-cal2org-directory))
         (py exactas-cal2org-python-executable)
         (output
          (with-output-to-string
            ;; process-file evita problemas de quoting del shell
            (process-file py nil standard-output nil script))))
    (insert output)))

(provide 'exactas-cal2org)
;;; exactas-cal2org.el ends here
