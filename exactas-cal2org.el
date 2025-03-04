;;; exactas_cal2org.el --- Description -*- lexical-binding: t; -*-
;;
;; Copyright (C) 2025 Pablo Cobelli
;;
;; Author: Pablo Cobelli <pablo.cobelli@gmail.com>
;; Maintainer: Pablo Cobelli <pablo.cobelli@gmail.com>
;; Created: March 04, 2025
;; Modified: March 04, 2025
;; Version: 0.0.1
;; Keywords: abbrev bib c calendar comm convenience data docs emulations extensions faces files frames games hardware help hypermedia i18n internal languages lisp local maint mail matching mouse multimedia news outlines processes terminals tex text tools unix vc
;; Homepage: https://github.com/pablocobelli/exactas_cal2org
;; Package-Requires: ((emacs "24.3"))
;;
;; This file is not part of GNU Emacs.
;;
;;; Commentary:
;;
;;  Description
;;
;;; Code:

(defvar exactas-cal2org-directory
  (file-name-directory (or load-file-name buffer-file-name))
  "Directory where the exactas-cal2org package is installed.")

(defun exactas-cal2org-run ()
  "Run exactas-cal2org.py and insert its output at the current cursor position."
  (interactive)
  (let* ((script (expand-file-name "exactas-cal2org.py" exactas-cal2org-directory))
         (output (shell-command-to-string (format "python3 %s" script))))
    (insert output)))  ;; Insert the script output at point

(provide 'exactas_cal2org)
;;; exactas_cal2org.el ends here
